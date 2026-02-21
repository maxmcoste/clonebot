"""CLI interface for CloneBot."""

import os
from pathlib import Path

os.environ["TOKENIZERS_PARALLELISM"] = "false"

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.live import Live
from rich.text import Text

from dotenv import load_dotenv

load_dotenv()

app = typer.Typer(name="clonebot", help="Digital Person Clone - Chat with memories")
console = Console()


@app.command()
def create(
    name: str = typer.Argument(help="Name of the clone to create"),
    description: str = typer.Option("", "--description", "-d", help="Description of the person"),
    traits: str = typer.Option("", "--traits", "-t", help="Comma-separated personality traits"),
    language: str = typer.Option("english", "--language", "-l", help="Response language (english, italian)"),
):
    """Create a new clone profile."""
    from clonebot.core.clone import CloneProfile, SUPPORTED_LANGUAGES

    lang = language.lower()
    if lang not in SUPPORTED_LANGUAGES:
        console.print(f"[red]Unsupported language '{language}'. Choose from: {', '.join(sorted(SUPPORTED_LANGUAGES))}[/red]")
        raise typer.Exit(1)

    personality = [t.strip() for t in traits.split(",") if t.strip()] if traits else []

    profile = CloneProfile(
        name=name,
        description=description,
        language=lang,
        personality_traits=personality,
    )
    path = profile.save()
    console.print(f"[green]Created clone '{name}' ({lang}) at {path.parent}[/green]")


@app.command(name="list")
def list_clones():
    """List all clone profiles."""
    from clonebot.core.clone import CloneProfile

    clones = CloneProfile.list_all()
    if not clones:
        console.print("[yellow]No clones found. Create one with: clonebot create <name>[/yellow]")
        return

    table = Table(title="Clones")
    table.add_column("Name", style="cyan")
    table.add_column("Language", style="magenta")
    table.add_column("Description")
    table.add_column("Traits")

    for clone in clones:
        table.add_row(
            clone.name,
            clone.language,
            clone.description or "-",
            ", ".join(clone.personality_traits) if clone.personality_traits else "-",
        )
    console.print(table)


@app.command()
def ingest(
    name: str = typer.Argument(help="Clone name"),
    path: str = typer.Argument(help="File or directory to ingest"),
    tags: str = typer.Option("", "--tags", "-t", help="Comma-separated tags (e.g. 'daughter,birthday')"),
    description: str = typer.Option("", "--description", "-d", help="Manual description of the media"),
    no_vision: bool = typer.Option(False, "--no-vision", help="Skip AI vision analysis (requires --description for media)"),
):
    """Ingest memory data into a clone."""
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, MofNCompleteColumn

    from clonebot.core.clone import CloneProfile
    from clonebot.memory.ingest import (
        ingest_file, ingest_directory,
        TEXT_EXTENSIONS, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS,
    )
    from clonebot.memory.validate import FileTypeMismatchError
    from clonebot.memory.embeddings import get_embedding_provider
    from clonebot.memory.store import VectorStore

    profile = CloneProfile.load(name)
    file_path = Path(path).resolve()

    if not file_path.exists():
        console.print(f"[red]Path not found: {file_path}[/red]")
        raise typer.Exit(1)

    # Parse tags
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

    # Validate: --no-vision on media files requires --description
    use_vision = not no_vision
    if no_vision and file_path.is_file():
        suffix = file_path.suffix.lower()
        if suffix in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS and not description:
            console.print("[red]--no-vision requires --description for media files[/red]")
            raise typer.Exit(1)

    # ------------------------------------------------------------------ #
    #  Directory ingestion — per-file progress bar with skip reporting    #
    # ------------------------------------------------------------------ #
    if file_path.is_dir():
        supported = TEXT_EXTENSIONS | IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
        files = [
            f for f in sorted(file_path.rglob("*"))
            if f.is_file() and f.suffix.lower() in supported
        ]

        if not files:
            console.print("[yellow]No supported files found in directory.[/yellow]")
            raise typer.Exit(1)

        chunks: list = []
        skipped: list[tuple[str, str]] = []  # (filename, reason)

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
            transient=False,
        ) as progress:
            task = progress.add_task("Scanning…", total=len(files))

            for f in files:
                progress.update(task, description=f"[cyan]{f.name}[/cyan]")
                try:
                    file_chunks = ingest_file(
                        f, tags=tag_list, description=description, use_vision=use_vision
                    )
                    chunks.extend(file_chunks)
                    progress.print(
                        f"  [green]✓[/green] {f.name} "
                        f"[dim]({len(file_chunks)} chunk{'s' if len(file_chunks) != 1 else ''})[/dim]"
                    )
                except FileTypeMismatchError as e:
                    skipped.append((f.name, str(e)))
                    progress.print(f"  [yellow]⚠ Skipped[/yellow]  {e}")
                except Exception as e:
                    skipped.append((f.name, str(e)))
                    progress.print(f"  [red]✗ Error[/red]    {f.name}: {e}")
                finally:
                    progress.advance(task)

            progress.update(task, description="Done")

        if skipped:
            console.print(
                f"\n[yellow]Skipped {len(skipped)} file(s) "
                f"({len(files) - len(skipped)} ingested successfully)[/yellow]"
            )
        if not chunks:
            console.print("[yellow]No data was ingested — all files were skipped.[/yellow]")
            raise typer.Exit(1)

    # ------------------------------------------------------------------ #
    #  Single-file ingestion                                               #
    # ------------------------------------------------------------------ #
    else:
        with console.status("[bold blue]Ingesting…"):
            try:
                chunks = ingest_file(
                    file_path, tags=tag_list, description=description, use_vision=use_vision
                )
            except FileTypeMismatchError as e:
                console.print(f"[red]File type mismatch — {e}[/red]")
                raise typer.Exit(1)

        if not chunks:
            console.print("[yellow]No data to ingest from the provided file.[/yellow]")
            raise typer.Exit(1)
        console.print(f"  Chunked into {len(chunks)} pieces")

    # ------------------------------------------------------------------ #
    #  Embed and store                                                     #
    # ------------------------------------------------------------------ #
    with console.status("[bold blue]Generating embeddings and storing…"):
        embedder = get_embedding_provider()
        store = VectorStore(profile.get_dir(), embedder)
        count = store.add_documents(chunks)

    console.print(f"[green]Ingested {count} chunks into '{name}'[/green]")


@app.command()
def stats(name: str = typer.Argument(help="Clone name")):
    """Show memory stats for a clone."""
    from clonebot.core.clone import CloneProfile
    from clonebot.memory.embeddings import get_embedding_provider
    from clonebot.memory.store import VectorStore

    profile = CloneProfile.load(name)
    embedder = get_embedding_provider()
    store = VectorStore(profile.get_dir(), embedder)
    info = store.stats()

    panel = Panel(
        f"[cyan]Clone:[/cyan] {profile.name}\n"
        f"[cyan]Language:[/cyan] {profile.language}\n"
        f"[cyan]Description:[/cyan] {profile.description or '-'}\n"
        f"[cyan]Traits:[/cyan] {', '.join(profile.personality_traits) or '-'}\n"
        f"[cyan]Total chunks:[/cyan] {info['total_chunks']}\n"
        f"[cyan]DB path:[/cyan] {info['db_path']}",
        title=f"Stats: {name}",
    )
    console.print(panel)


@app.command()
def chat(
    name: str = typer.Argument(help="Clone name"),
    provider: str = typer.Option(None, "--provider", "-p", help="LLM provider override"),
    model: str = typer.Option(None, "--model", "-m", help="Model name override"),
):
    """Start an interactive chat session with a clone."""
    from clonebot.core.clone import CloneProfile
    from clonebot.core.session import ChatSession
    from clonebot.memory.embeddings import get_embedding_provider
    from clonebot.memory.store import VectorStore
    from clonebot.rag.retriever import Retriever
    from clonebot.llm.provider import get_llm_provider
    from clonebot.config.settings import get_settings

    settings = get_settings()
    if provider:
        settings.llm_provider = provider
    if model:
        settings.llm_model = model

    profile = CloneProfile.load(name)
    embedder = get_embedding_provider()
    store = VectorStore(profile.get_dir(), embedder)
    retriever = Retriever(store)
    llm = get_llm_provider()

    session = ChatSession(
        clone=profile,
        llm=llm,
        store=store,
        retriever=retriever,
    )

    console.print(Panel(
        f"Chatting with [bold cyan]{profile.name}[/bold cyan]\n"
        f"Language: {profile.language}\n"
        f"Memories: {store.count()} chunks loaded\n"
        f"Provider: {settings.llm_provider} / {settings.llm_model}\n"
        f"Type [bold]quit[/bold] or [bold]exit[/bold] to end",
        title="CloneBot Chat",
    ))

    while True:
        try:
            user_input = Prompt.ask(f"\n[bold green]You[/bold green]")
        except (KeyboardInterrupt, EOFError):
            break

        if user_input.strip().lower() in ("quit", "exit", "q"):
            break

        if not user_input.strip():
            continue

        console.print(f"\n[bold cyan]{profile.name}[/bold cyan]", end="")
        try:
            response_text = Text()
            with Live(response_text, console=console, refresh_per_second=15) as live:
                for chunk in session.chat_stream(user_input):
                    response_text.append(chunk)
                    live.update(response_text)
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")

    console.print("\n[dim]Chat ended.[/dim]")


if __name__ == "__main__":
    app()
