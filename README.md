# Albert Obsidian
![](demo.png)

A fairly simple python plugin to allow [albert](https://github.com/albertlauncher/albert) to interact with an [Obsidian](https://obsidian.md/) vault.
Currently supports the following features
- Trigger query search of vault notes (default `obs`) by name/tags/body
    - Allows opening of searched note directly in obsidian
- Global query results from vault notes via name/tags/body
    - Allows opening of searched note directly in obsidian
- Creating a new note from query string:

![](new-note.png)

## Install

In order for this plugin to work, your Obsidian install  must be setup to [allow usage of Obsidian URI protocol](https://help.obsidian.md/Concepts/Obsidian+URI)
Run the follow from a terminal:

```shell
git clone https://github.com/Pete-Hamlin/albert-obsidian.git $HOME/.local/share/albert/python/plugins/obsidian
```

Then enable the plugin from the albert settings panel (you **must** enable the python plugin for this plugin to be loadable)

## Settings

## Future Work

Potential ideas to add in future versions:
- [ ]  Open search directly in Obsidian
- [ ] Vault selector via query
