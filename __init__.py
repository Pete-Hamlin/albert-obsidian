"""
Obsidian plugin for Albert launcher.

Searches notes in an Obsidian vault. Allows for creation of new notes in the selected vault.

"""

from pathlib import Path
from urllib import parse
from threading import Thread, Event
from time import perf_counter_ns
from watchfiles import Change, DefaultFilter, watch
from yaml.constructor import ConstructorError

import frontmatter
from albert import *

md_iid = "2.3"
md_version = "1.5"
md_name = "Obsidian"
md_description = "Search/add notes in a Obsidian vault."
md_url = "https://github.com/Pete-Hamlin/albert-obsidian.git"
md_license = "MIT"
md_authors = ["@Pete-Hamlin"]
md_lib_dependencies = ["python-frontmatter", "watchfiles"]


class Note:
    def __init__(self, path: Path, body) -> None:
        self.path = path
        self.body = body


class CDFilter(DefaultFilter):
    """
    When it comes to indexing, we don't care about updates to the file, so this filter
    allows us to just watch for create/delete events and re-index accordingly when they happen
    """

    allowed_changes = [Change.added, Change.deleted]

    def __call__(self, change: Change, path: str) -> bool:
        return change in self.allowed_changes and super().__call__(change, path)


class FileWatcherThread(Thread):
    def __init__(self, callback, path, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.__stop_event = Event()
        self.__callback = callback
        self.__path = path

    def run(self):
        # Watch for file changes and re-index
        for _ in watch(self.__path, watch_filter=CDFilter(), stop_event=self.__stop_event):
            self.__callback()

    def stop(self):
        self.__stop_event.set()


class Plugin(PluginInstance, IndexQueryHandler):
    iconUrls = [
        f"file:{Path(__file__).parent}/obsidian.png",
        "xdg:folder-documents",
    ]

    def __init__(self):
        PluginInstance.__init__(self)
        IndexQueryHandler.__init__(
            self, id=self.id, name=self.name, description=self.description, defaultTrigger="obs ", synopsis="<note>"
        )

        self._root_dir = self.readConfig("root_dir", str) or ""
        self._open_override = self.readConfig("open_override", str) or "xdg-open"
        self._config_dir = self.readConfig("config_dir", str) or ""
        self._filter_by_tags = self.readConfig("filter_by_tags", bool) or True
        self._filter_by_body = self.readConfig("filter_by_body", bool) or False

        self.root_path = Path(self._root_dir)
        self.thread = FileWatcherThread(self.updateIndexItems, self._root_dir)
        self.thread.start()

    def __del__(self):
        self.thread.stop()
        self.thread.join()

    @property
    def root_dir(self):
        return self._root_dir

    @root_dir.setter
    def root_dir(self, value):
        self._root_dir = value
        self.writeConfig("root_dir", value)

        self.root_path = Path(value)
        self.thread.stop()
        self.thread.join()
        self.thread = FileWatcherThread(self.updateIndexItems, self._root_dir)
        self.thread.start()

    @property
    def open_override(self):
        return self._open_override

    @open_override.setter
    def open_override(self, value):
        self._open_override = value
        self.writeConfig("open_override", value)

    @property
    def filter_by_tags(self):
        return self._filter_by_tags

    @filter_by_tags.setter
    def filter_by_tags(self, value):
        self._filter_by_tags = value
        self.writeConfig("filter_by_tags", value)

    @property
    def filter_by_body(self):
        return self._filter_by_body

    @filter_by_body.setter
    def filter_by_body(self, value):
        self._filter_by_body = value
        self.writeConfig("filter_by_body", value)

    def configWidget(self):
        return [
            {"type": "lineedit", "property": "root_dir", "label": "Path to notes vault"},
            {"type": "lineedit", "property": "open_override", "label": "Open command to run Obsidian URI"},
            {"type": "checkbox", "property": "filter_by_tags", "label": "Filter by note tags"},
            {"type": "checkbox", "property": "filter_by_body", "label": "Filter by note body"},
        ]

    def updateIndexItems(self):
        start = perf_counter_ns()
        notes = self.parse_notes()
        index_items = []

        for note in notes:
            filter = self.create_filters(note)
            item = self.gen_item(note)
            index_items.append(IndexItem(item=item, string=filter))
        self.setIndexItems(index_items)
        info("Indexed {} notes [{:d} ms]".format(len(index_items), (int(perf_counter_ns() - start) // 1000000)))

    def handleTriggerQuery(self, query):
        # Trigger query will ignore the index and always check against the latest vault state
        stripped = query.string.strip()
        if stripped:
            if not query.isValid:
                return
            data = self.parse_notes()
            notes = (item for item in data if all(filter in self.create_filters(item) for filter in query.string.split()))
            items = [self.gen_item(item) for item in notes]
            text = parse.urlencode({"vault": self.root_path.name, "name": stripped}, quote_via=parse.quote)
            run_args = self._open_override.split() + [f"obsidian://new?{text}"]
            query.add(items)
            query.add(
                StandardItem(
                    id=self.id,
                    text="Create new Note",
                    subtext=f"{str(self.root_path)}/{stripped}",
                    iconUrls=["xdg:accessories-text-editor"],
                    actions=[
                        Action(
                            "create",
                            "Create note",
                            lambda args=run_args: runDetachedProcess(args),
                        )
                    ],
                )
            )
        else:
            query.add(
                StandardItem(id=self.id, text=self.name, subtext="Search for a note in Obsidian", iconUrls=self.iconUrls)
            )

    def parse_notes(self):
        for item in self.root_path.rglob("*.md"):
            try:
                yield Note(item, frontmatter.load(item))
            except ConstructorError:
                warning(f"Unable to parse {item.name} - skipping")

    def create_filters(self, note: Note) -> str:
        filters, tags = note.path.name, note.body.get("tags")
        if self._filter_by_tags and tags:
            if isinstance(tags, list):
                filters += ",".join(tags)
            else:
                filters += str(tags)
        if self._filter_by_body:
            filters += note.body.content
        return filters.lower()

    def gen_item(self, note: Note):
        tags = note.body.get("tags")
        if tags:
            subtext = " - ".join([str(note.path), ",".join(tags)])
        else:
            subtext = str(note.path)
        note_uri = "obsidian://open?{}".format(parse.urlencode({"vault": self.root_path.name, "file": note.path.name}, quote_via=parse.quote))
        run_args = self._open_override.split() + [note_uri]
        return StandardItem(
            id=self.id,
            text=note.path.name.replace(".md", ""),
            subtext=subtext,
            iconUrls=self.iconUrls,
            actions=[
                Action(
                    "open",
                    "Open",
                    lambda args=run_args: runDetachedProcess(args),
                ),
                Action("copy", "Copy URI", lambda uri=note_uri: setClipboardText(uri)),
            ],
        )
