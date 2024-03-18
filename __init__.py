"""
Obsidian plugin for Albert launcher.

Searches notes in an Obsidian vault. Allows for creation of new notes in the selected vault.

"""

from pathlib import Path
from urllib import parse

import frontmatter
from albert import *

md_iid = "2.1"
md_version = "0.5"
md_name = "Obsidian"
md_id = "obsidian"
md_description = "Search/add notes in a Obsidian vault."
md_license = "MIT"
md_maintainers = ["@Pete-Hamlin"]
md_lib_dependencies = ["python-frontmatter"]


class Note:
    def __init__(self, path: Path, body) -> None:
        self.path = path
        self.body = body


class Plugin(PluginInstance, GlobalQueryHandler):
    iconUrls = [
        f"file:{Path(__file__).parent}/obsidian.png",
        "xdg:folder-documents",
    ]

    def __init__(self):
        GlobalQueryHandler.__init__(self, id=md_id, name=md_name, description=md_description, defaultTrigger="obs ")
        PluginInstance.__init__(self, extensions=[self])

        self._root_dir = self.readConfig("root_dir", str) or ""
        self._open_override = self.readConfig("open_override", str) or "xdg-open"
        self._config_dir = self.readConfig("config_dir", str) or ""
        self._filter_by_tags = self.readConfig("filter_by_tags", bool) or True
        self._filter_by_body = self.readConfig("filter_by_body", bool) or False

        self.root_path = Path(self._root_dir)

    @property
    def root_dir(self):
        return self._root_dir

    @root_dir.setter
    def root_dir(self, value):
        self._root_dir = value
        self.writeConfig("root_dir", value)
        self.root_path = Path(value)

    @property
    def open_override(self):
        return self._open_override

    @open_override.setter
    def open_override(self, value):
        self._open_override = value
        self.writeConfig("open_override", value)
        self.root_path = Path(value)

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

    def handleTriggerQuery(self, query):
        stripped = query.string.strip()
        if stripped:
            if not query.isValid:
                return
            data = self.parse_notes()
            notes = (item for item in data if stripped.lower() in self.create_filters(item))
            items = [item for item in self.gen_items(notes)]
            text = parse.urlencode({"vault": self.root_path.name, "name": stripped}, quote_via=parse.quote)
            run_args = self._open_override.split() + [f"obsidian://new?{text}"]
            query.add(items)
            query.add(
                StandardItem(
                    id=md_id,
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
                StandardItem(id=md_id, text=md_name, subtext="Search for a note in Obsidian", iconUrls=self.iconUrls)
            )

    def handleGlobalQuery(self, query):
        stripped = query.string.strip()
        if stripped:
            if not query.isValid:
                return
            data = self.parse_notes()
            notes = (item for item in data if stripped.lower() in self.create_filters(item))
            items = [RankItem(item=item, score=0) for item in self.gen_items(notes)]
            return items

    def parse_notes(self):
        for item in self.root_path.rglob("*.md"):
            yield Note(item, frontmatter.load(item))

    def create_filters(self, note: Note):
        filters, tags = str(note.path), note.body.get("tags")
        if self._filter_by_tags and tags:
            if isinstance(tags, list):
                filters += ",".join(tags)
            else:
                filters += str(tags)
        if self._filter_by_body:
            filters += note.body.content
        return filters.lower()

    def gen_items(self, notes: list[Note]):
        for note in notes:
            tags = note.body.get("tags")
            if tags:
                subtext = " - ".join([str(note.path), ",".join(tags)])
            else:
                subtext = str(note.path)
            note_uri = parse.urlencode({"vault": self.root_path.name, "file": note.path.name}, quote_via=parse.quote)
            run_args = self._open_override.split() + [f"obsidian://open?{note_uri}"]
            yield StandardItem(
                id=md_id,
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
