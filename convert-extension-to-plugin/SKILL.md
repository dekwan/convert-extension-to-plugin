---
name: convert-extension-to-plugin
description: Convert Gemini CLI extension source code into Antigravity Plugins source code
---

This skill converts a Gemini CLI extension source repository into an Antigravity Plugin source repository.

> [!IMPORTANT]
> **SAFETY GUARANTEE**: This skill NEVER modifies the original source directory. The helper script copies the source repository to the destination directory first and executes all conversion/migration steps strictly inside the destination folder. The original repository is preserved completely untouched.

## Usage

To use this skill, execute the helper script `scripts/convert.py` with the path to the extension repository and the destination directory:

```bash
python3 <skill_dir>/scripts/convert.py <src_path> <dest_path>
```

where `<skill_dir>` is the absolute path to this skill directory (e.g. `.agents/skills/convert-gemini-extension`).

> [!IMPORTANT]
> **CRITICAL RULE**: The destination directory (`<dest_path>`) MUST have the exact same folder name (basename) as the source directory (`<src_path>`). For example, when migrating `extensions/my-extension`, the destination folder should be named `my-extension` (e.g., `migrated_plugins/my-extension`). Do NOT rename the destination folder to match the plugin's internal name (like `my-extension-plugin`).


## What the Skill Does

1. **Config Conversion**:
   - Reads `gemini-extension.json` and generates `plugin.json` containing the plugin's name.
   - Generates `mcp_config.json` with translated `mcpServers` settings. The translation maps `${extensionPath}` to `[YOUR_PLUGIN_PATH]/plugins/<plugin_name>/` literally (configurations containing `httpUrl` are copied with `httpUrl` renamed to `serverUrl`).

2. **Command Conversion**:
   - Recursively reads all command `.toml` files under the `commands/` directory.
   - Converts each command TOML to a skill (under `skills/<command_name>/SKILL.md`) with name/description frontmatter and the prompt as the body.
   - Removes the `commands/` directory from the source code.

3. **Hook Relocation**:
   - Moves files from the `hooks/` folder to the root/parent folder of the plugin and deletes the `hooks/` folder.

4. **Release Script Modification**:
   - Automatically detects and updates release scripts (like `release.js` or `release.ts`).
   - Replaces `gemini-extension.json` generation logic with `plugin.json` and `mcp_config.json` generation.
   - Reconfigures the release generator to package the MCP server command in a shell wrapper (`sh -c`) using the global plugins folder for portable installations.
   - Removes the copy of the `commands/` directory.
   - Redirects copying of the context markdown file (like `my-context.md`) to be copied into the archive's `rules/` directory.
   - Redirects the release directory to be created outside the plugin source folder (e.g. `../<plugin_source_folder_name>-release/`).
   - Ensures the base name of the packaged release folder (and the generated archive file itself) matches the official plugin name specified in `plugin.json` (e.g. `my-extension`).
   - Adds Node 22 compatibility for the `archiver` library if it's used.

5. **Reference Correction**:
   - Replaces any references to `gemini-extension.json` with `mcp_config.json` in all source files, script files, and configurations.

6. **Automatic Release Packaging & Cleanup**:
   - Creates or updates a root `package.json` with a dynamically generated `"release"` script that packages only the runtime files.
   - Installs dependencies and runs the release command (`npm run release` or `npm run release:dev`) to build the release archive outside the source folder.
   - Recursively deletes all build artifacts (`dist/`) and packages (`node_modules/`) from the migrated source tree, leaving it in a pristine state.
