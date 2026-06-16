# Convert Extension to Plugin

An agent skill and command-line helper designed to convert Gemini CLI extensions into Antigravity Plugins.

This tool automates the migration of your extension codebase to the Antigravity plugin ecosystem. It handles configuration mapping, command-to-skill translation, hook relocations, release script updates, and dependencies packaging.

---

## Repository Structure

- `convert-extension-to-plugin/SKILL.md`: The core instruction file loaded by the agent to understand and run the skill.
- `convert-extension-to-plugin/scripts/convert.py`**`: The Python migration helper script executing the conversion.

---

## Safety Guarantee

**Zero Modification Policy**: This agent skill should not your original source directory. The migration script `convert.py` automatically creates a copy of the source repository in your specified destination folder and performs all operations within that folder.

---

## Installation & Discovery

To make this skill discoverable by your Antigravity agent:

1. Copy the `convert-extension-to-plugin` directory into one of the customization roots:
   - **Global Customizations**: `~/.gemini/config/skills/convert-extension-to-plugin`
   - **Workspace Customizations**: `<your_workspace_root>/.agents/skills/convert-extension-to-plugin`
2. Restart or invoke the agent. The skill will automatically be registered under the name `convert-extension-to-plugin`.

---

## Usage

### Agent Interaction
Ask the agent to execute this skill for you. For example:
> "Convert the extension source code at `/path/to/my-extension` into a plugin using the `convert-extension-to-plugin` skill."

### Command Line
You can also run the migration script `convert.py` directly using Python 3:

```bash
python3 convert-extension-to-plugin/scripts/convert.py <src_path> <dest_path>
```

---

## What the Migration Script Does

### 1. Configuration Conversion
- Detects and parses `gemini-extension.json` (or fallback to `mcp_config.json` / `package.json`).
- Automatically creates `plugin.json` containing the plugin metadata.
- Generates `mcp_config.json` with translated `mcpServers` settings. Variable references like `${extensionPath}` and `\${extensionPath}` are converted to `[YOUR_PLUGIN_PATH]/plugins/<plugin_name>/` to ensure portability.

### 2. Commands to Skills Conversion
- Recursively scans the `commands/` directory for any TOML command definition files.
- Converts each command TOML into an individual agent skill at `skills/<command_name>/SKILL.md`. The description and instructions frontmatter are extracted and structured accordingly.
- Removes the deprecated `commands/` directory.

### 3. Hook Relocation
- Moves hook scripts from the `hooks/` folder to the root/parent folder of the plugin and cleans up the directory.

### 4. Release Script Modification
- Scans for and updates release scripts (e.g. `release.js` or `release.ts`).
- Modifies config file generations to target `plugin.json` and `mcp_config.json`.
- Repackages release archives to write files to `/rules/` and places the generated release outside the source tree (e.g. `../<plugin_name>-release/`).
- Integrates Node 22 compatibility for the `archiver` library.

### 5. Code Reference Correction
- Replaces static file references of `gemini-extension.json` with `mcp_config.json` across configuration files, documentation, scripts, and source files.

### 6. Packaging & Cleanup
- Adds/updates the `"release"` script in `package.json`.
- Runs dependency installation (`npm install`) and builds the release (`npm run release` or `npm run release:dev`).
- Cleans up temporary build directories (`node_modules/` and `dist/`) inside the migrated source tree to keep it clean.
