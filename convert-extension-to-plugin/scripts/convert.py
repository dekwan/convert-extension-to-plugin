# SAFETY GUARANTEE: This script NEVER modifies the original source directory.
# It copies the source repository to the destination directory first and executes
# all conversion/migration steps strictly inside the destination folder.

import os
import json
import re
import shutil
import sys

def convert_toml_to_skill(toml_path, skills_dir, name):
    with open(toml_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    description = ""
    prompt = ""
    
    desc_match = re.search(r'description\s*=\s*"(.*?)"', content, re.DOTALL)
    if not desc_match:
        desc_match = re.search(r"description\s*=\s*'(.*?)'", content, re.DOTALL)
    if desc_match:
        description = desc_match.group(1).strip()
        
    prompt_match = re.search(r'prompt\s*=\s*"""(.*?)"""', content, re.DOTALL)
    if not prompt_match:
        prompt_match = re.search(r"prompt\s*=\s*'''(.*?)'''", content, re.DOTALL)
    if not prompt_match:
        prompt_match = re.search(r'prompt\s*=\s*"(.*?)"', content, re.DOTALL)
    if not prompt_match:
        prompt_match = re.search(r"prompt\s*=\s*'(.*?)'", content, re.DOTALL)
    if prompt_match:
        prompt = prompt_match.group(1).strip()

    skill_dir = os.path.join(skills_dir, name)
    os.makedirs(skill_dir, exist_ok=True)
    
    skill_md_path = os.path.join(skill_dir, 'SKILL.md')
    with open(skill_md_path, 'w', encoding='utf-8') as f:
        f.write('---\n')
        f.write(f'name: {name}\n')
        f.write(f'description: {description}\n')
        f.write('---\n')
        f.write(prompt + '\n')
    print(f"Converted command {toml_path} to skill {skill_md_path}")

def convert_mcp_config(gemini_json, name):
    mcp_servers = gemini_json.get('mcpServers', {})
    converted_servers = {}
    
    for srv_name, srv_conf in mcp_servers.items():
        if 'httpUrl' in srv_conf or 'serverUrl' in srv_conf:
            srv_conf_copy = srv_conf.copy()
            if 'httpUrl' in srv_conf_copy:
                srv_conf_copy['serverUrl'] = srv_conf_copy.pop('httpUrl')
            converted_servers[srv_name] = srv_conf_copy
            continue
            
        cmd = srv_conf.get('command', '')
        args = srv_conf.get('args', [])
        cwd = srv_conf.get('cwd', '')
        env = srv_conf.get('env', None)
        
        new_args = []
        for arg in args:
            arg_clean = arg.replace('${/}', '/').replace('\\${/}', '/')
            replaced = arg_clean.replace('${extensionPath}', f"[YOUR_PLUGIN_PATH]/plugins/{name}/").replace('//', '/')
            new_args.append(replaced)
        
        cwd_clean = cwd.replace('${/}', '/').replace('\\${/}', '/').replace('${extensionPath}', f"[YOUR_PLUGIN_PATH]/plugins/{name}/").replace('\\${extensionPath}', f"[YOUR_PLUGIN_PATH]/plugins/{name}/").replace('//', '/')
        
        converted_servers[srv_name] = {
            "command": cmd,
            "args": new_args,
            "cwd": cwd_clean,
            "env": env
        }
        
    return {
        "mcpServers": converted_servers
    }

def update_release_script(file_path, name):
    print(f"Updating release script: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Locate write of gemini-extension.json or mcp_config.json
    write_pattern = r'fs\.writeFileSync\(\s*path\.join\([^,]+,\s*[\'"](?:gemini-extension\.json|mcp_config\.json)[\'"]\),\s*JSON\.stringify\(([^,]+),\s*null,\s*2\),?\s*\);?'
    match = re.search(write_pattern, content)
    if match:
        var_name = match.group(1).strip()
        write_call_start = match.start()
        write_call_end = match.end()
        
        replacement_template = """
  // Generate the plugin.json file
  const pluginJson = {
    name: '{name}'
  };
  fs.writeFileSync(
    path.join(archiveDir, 'plugin.json'),
    JSON.stringify(pluginJson, null, 2),
  );

  // Generate the mcp_config.json file
  const mcpConfigJson = {
    mcpServers: {var_name}.mcpServers
  };
  const mcpConfigStr = JSON.stringify(mcpConfigJson, null, 2)
    .replace(/\\${extensionPath}/g, '[YOUR_PLUGIN_PATH]/plugins/{name}/')
    .replace(/\\\\\\${extensionPath}/g, '[YOUR_PLUGIN_PATH]/plugins/{name}/')
    .replace(/\\${PlatformExtensionPath}/g, '[YOUR_PLUGIN_PATH]/plugins/{name}/')
    .replace(/\\\\\\${PlatformExtensionPath}/g, '[YOUR_PLUGIN_PATH]/plugins/{name}/')
    .replace(/\\${/g, '/')
    .replace(/\\\\\\${/g, '/')
    .replace(/\\/\\//g, '/');
  fs.writeFileSync(
    path.join(archiveDir, 'mcp_config.json'),
    mcpConfigStr,
  );
"""
        replacement_js = replacement_template.replace('{var_name}', var_name).replace('{name}', name)
        content_before = content[:write_call_start]
        content_after = content[write_call_end:]
        content = content_before + replacement_js + content_after
        print("Replaced config file write call with plugin.json and mcp_config.json generation in release script.")

    # 2. Remove copying of the commands directory
    exact_block_1 = """  // Copy the commands directory
  const commandsDir = path.join(rootDir, 'commands');
  if (fs.existsSync(commandsDir)) {
    fs.cpSync(commandsDir, path.join(archiveDir, 'commands'), {
      recursive: true,
    });
  }"""

    content_stripped = '\n'.join([line.rstrip() for line in content.splitlines()])
    exact_block_stripped = '\n'.join([line.rstrip() for line in exact_block_1.splitlines()])
    
    if exact_block_stripped in content_stripped:
        pattern = re.escape(exact_block_stripped).replace(r'\ ', r'\s*').replace(r'\n', r'\s*\n\s*')
        content, count = re.subn(pattern, '', content, flags=re.DOTALL)
        if count > 0:
            print("Removed commands directory copying (exact match).")
    else:
        commands_copy_pattern = r'//\s*Copy\s+the\s+commands\s+directory\s*\n\s*const\s+commandsDir\s*=[^\n]+\n\s*if\s*\(\s*fs\.existsSync\(\s*commandsDir\s*\)\s*\)\s*\{[^{}]*fs\.cpSync\(\s*commandsDir,\s*path\.join\(\s*archiveDir,\s*[\'"]commands[\'"]\s*\),\s*\{[^{}]*\}\s*\);\s*\}'
        content, count = re.subn(commands_copy_pattern, '', content, flags=re.DOTALL)
        if count > 0:
            print("Removed commands directory copying (regex 1).")
        else:
            simple_pattern = r'const\s+commandsDir\s*=\s*path\.join\(rootDir,\s*[\'"]commands[\'"]\);\s*if\s*\(\s*fs\.existsSync\(commandsDir\)\s*\)\s*\{[^}]*\}'
            content, count = re.subn(simple_pattern, '', content, flags=re.DOTALL)
            if count > 0:
                print("Removed commands directory copying (regex 2).")

    # 3. Update copy of WORKSPACE-Context.md / other context files to rules/ folder inside archiveDir
    copy_md_pattern = r'fs\.copyFileSync\(\s*(path\.join\([^,]+,\s*[\'"]([^\'"]+\.md)[\'"]\)),\s*path\.join\(archiveDir,\s*[\'"]\2[\'"]\),?\s*\);?'
    copy_md_replacement = r"""fs.mkdirSync(path.join(archiveDir, 'rules'), { recursive: true });
  fs.copyFileSync(
    \1,
    path.join(archiveDir, 'rules', '\2'),
  );"""
    content, count = re.subn(copy_md_pattern, copy_md_replacement, content)
    if count > 0:
        print("Replaced individual MD context file copying with rules/ directory copying.")

    # 4. Fix Node 22 ESM archiver require call
    archiver_pattern = r'const\s+archive\s*=\s*archiver\(\s*[\'"]tar[\'"]\s*,\s*\{\s*gzip:\s*true,?\s*\}\s*\);?'
    archiver_replacement = "const archive = typeof archiver === 'function' ? archiver('tar', { gzip: true }) : new archiver.TarArchive({ gzip: true });"
    content, count = re.subn(archiver_pattern, archiver_replacement, content)
    if count > 0:
        print("Updated archiver initialization for Node 22 compatibility.")

    # 5. Redirect release folder outside of the plugin directory
    release_dir_pattern = r'const\s+releaseDir\s*=\s*path\.join\(rootDir,\s*[\'"]release[\'"]\);?'
    release_dir_replacement = "const releaseDir = path.join(rootDir, '..', `${path.basename(rootDir)}-release`);"
    content, count = re.subn(release_dir_pattern, release_dir_replacement, content)
    if count > 0:
        print("Redirected release directory outside of the plugin root folder.")

    # 6. Make sure the baseName in the release script matches the plugin's name
    basename_pattern = r'const\s+baseName\s*=\s*[\'"][^\'"]+[\'"];?'
    basename_replacement = f"const baseName = '{name}';"
    content, count = re.subn(basename_pattern, basename_replacement, content)
    if count > 0:
        print(f"Updated release script baseName to '{name}' to match plugin.json.")

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

def has_release_script(repo_path):
    for root, dirs, files in os.walk(repo_path):
        if 'node_modules' in root or '.git' in root or 'dist' in root:
            continue
        for file in files:
            if file in ('release.js', 'release.ts'):
                return True
    return False

def convert_extension(src_path, dest_path):
    print(f"Starting conversion from {src_path} to {dest_path}")
    
    # 0. Copy src_path to dest_path (ignoring .git, .github, and root node_modules)
    if os.path.exists(dest_path):
        shutil.rmtree(dest_path)
    shutil.copytree(src_path, dest_path, ignore=shutil.ignore_patterns('.git', '.github', 'node_modules'))
    print(f"Copied source files to {dest_path}")

    repo_path = dest_path
    gemini_json_path = os.path.join(repo_path, 'gemini-extension.json')
    if not os.path.exists(gemini_json_path):
        gemini_json_path = os.path.join(repo_path, 'mcp_config.json')
        
    if not os.path.exists(gemini_json_path):
        print(f"Warning: neither gemini-extension.json nor mcp_config.json found in {repo_path}")
        package_json_path = os.path.join(repo_path, 'package.json')
        if os.path.exists(package_json_path):
            with open(package_json_path, 'r', encoding='utf-8') as f:
                pkg = json.load(f)
                name = pkg.get('name', '').replace('-extension', '')
        else:
            name = os.path.basename(os.path.abspath(repo_path))
        gemini_json = {}
    else:
        with open(gemini_json_path, 'r', encoding='utf-8') as f:
            gemini_json = json.load(f)
        name = gemini_json.get('name', os.path.basename(os.path.abspath(repo_path)))

    # 1. Handle moving contextFileName to rules/ (only if this repository does NOT generate a release)
    is_release_builder = has_release_script(repo_path)
    context_file_name = gemini_json.get('contextFileName', '')
    if context_file_name and not is_release_builder:
        normalized_context_file_name = context_file_name.replace('${/}', '/').replace('\\${/}', '/')
        source_context_path = os.path.join(repo_path, normalized_context_file_name)
        if os.path.exists(source_context_path):
            rules_dir = os.path.join(repo_path, 'rules')
            os.makedirs(rules_dir, exist_ok=True)
            target_context_path = os.path.join(rules_dir, os.path.basename(source_context_path))
            shutil.move(source_context_path, target_context_path)
            print(f"Moved context file {normalized_context_file_name} to rules/{os.path.basename(source_context_path)}")
            # Clean up empty parent directory if applicable
            parent_dir = os.path.dirname(source_context_path)
            if parent_dir != repo_path and not os.listdir(parent_dir):
                try:
                    os.rmdir(parent_dir)
                    print(f"Cleaned up empty directory: {parent_dir}")
                except Exception:
                    pass

    # 2. Create plugin.json
    plugin_json = {"name": name}
    with open(os.path.join(repo_path, 'plugin.json'), 'w', encoding='utf-8') as f:
        json.dump(plugin_json, f, indent=2)
    print("Created plugin.json")

    # 3. Create mcp_config.json if mcpServers exists
    if 'mcpServers' in gemini_json:
        mcp_config = convert_mcp_config(gemini_json, name)
        with open(os.path.join(repo_path, 'mcp_config.json'), 'w', encoding='utf-8') as f:
            json.dump(mcp_config, f, indent=2)
        print("Created mcp_config.json")

    # 4. Convert commands to skills, with duplicate detection
    commands_dir = os.path.join(repo_path, 'commands')
    skills_dir = os.path.join(repo_path, 'skills')
    os.makedirs(skills_dir, exist_ok=True)
    
    if os.path.exists(commands_dir):
        toml_files = []
        name_counts = {}
        for root, dirs, files in os.walk(commands_dir):
            for file in files:
                if file.endswith('.toml'):
                    cmd_name = os.path.splitext(file)[0]
                    toml_path = os.path.join(root, file)
                    rel_dir = os.path.dirname(os.path.relpath(toml_path, commands_dir))
                    toml_files.append((toml_path, cmd_name, rel_dir))
                    name_counts[cmd_name] = name_counts.get(cmd_name, 0) + 1
                    
        for toml_path, cmd_name, rel_dir in toml_files:
            if name_counts[cmd_name] > 1:
                parent_dir_name = os.path.basename(rel_dir) if rel_dir else ""
                if parent_dir_name:
                    final_name = f"{parent_dir_name}-{cmd_name}"
                else:
                    final_name = cmd_name
            else:
                final_name = cmd_name
            convert_toml_to_skill(toml_path, skills_dir, final_name)
            
        shutil.rmtree(commands_dir)
        print("Removed commands/ directory")

    # 5. Relocate hooks/ to root if exists
    hooks_dir = os.path.join(repo_path, 'hooks')
    if os.path.exists(hooks_dir):
        for file in os.listdir(hooks_dir):
            src_file = os.path.join(hooks_dir, file)
            dest_file = os.path.join(repo_path, file)
            shutil.move(src_file, dest_file)
            print(f"Moved hook {file} to root")
        shutil.rmtree(hooks_dir)
        print("Removed hooks/ directory")

    # 6. Clean up gemini-extension.json
    orig_gemini_json_path = os.path.join(repo_path, 'gemini-extension.json')
    if os.path.exists(orig_gemini_json_path):
        os.remove(orig_gemini_json_path)
        print("Removed gemini-extension.json")

    # 7. Find and update release script if exists
    for root, dirs, files in os.walk(repo_path):
        if 'node_modules' in root or '.git' in root or 'dist' in root:
            continue
        for file in files:
            if file in ('release.js', 'release.ts'):
                update_release_script(os.path.join(root, file), name)

    # 8. Find and replace code references to gemini-extension.json in other files
    for root, dirs, files in os.walk(repo_path):
        if 'node_modules' in root or '.git' in root or 'dist' in root:
            continue
        for file in files:
            file_path = os.path.join(root, file)
            if file in ('release.js', 'release.ts'):
                continue
            if file.endswith(('.ts', '.js', '.json', '.md', '.yaml', '.yml', '.sh')):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                    if 'gemini-extension.json' in file_content:
                        new_content = file_content.replace('gemini-extension.json', 'mcp_config.json')
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        print(f"Updated reference to gemini-extension.json in {file_path}")
                except Exception as e:
                    print(f"Error updating file {file_path}: {e}")

    # 9. Handle Release Generation and source folder cleanup
    import subprocess
    package_json_path = os.path.join(repo_path, 'package.json')
    src_folder_name = os.path.basename(os.path.abspath(src_path))
    
    # Generate dynamic release command
    import shlex
    ignored_items = ['.git', '.github', 'node_modules', 'package-lock.json', 'release', f"{src_folder_name}-release"]
    items_to_copy = [shlex.quote(item) for item in os.listdir(repo_path) if item not in ignored_items]
    items_str = ' '.join(items_to_copy)
    
    dynamic_release_cmd = f"mkdir -p ../{src_folder_name}-release/{name} && cp -r {items_str} ../{src_folder_name}-release/{name} && tar -cvzf ../{src_folder_name}-release/{name}.tar.gz -C ../{src_folder_name}-release {name} && rm -rf ../{src_folder_name}-release/{name}"

    if not os.path.exists(package_json_path):
        # Create minimal package.json
        pkg_data = {
            "name": name,
            "version": "1.0.0",
            "description": f"Antigravity plugin for {name}",
            "scripts": {
                "release": dynamic_release_cmd
            }
        }
        with open(package_json_path, 'w', encoding='utf-8') as f:
            json.dump(pkg_data, f, indent=2)
        print("Created release package.json")
    else:
        # Update existing package.json
        with open(package_json_path, 'r', encoding='utf-8') as f:
            pkg_data = json.load(f)
        
        scripts = pkg_data.get('scripts', {})
        if 'release' not in scripts:
            prefix = ""
            if 'install-deps' in scripts:
                prefix += "npm run install-deps && "
            if 'build' in scripts:
                prefix += "npm run build && "
            
            scripts['release'] = prefix + dynamic_release_cmd
            pkg_data['scripts'] = scripts
            with open(package_json_path, 'w', encoding='utf-8') as f:
                json.dump(pkg_data, f, indent=2)
            print("Updated existing package.json with release script")

    # Install dependencies and run release script
    print("Installing dependencies...")
    try:
        subprocess.run(['npm', 'install'], cwd=repo_path, check=True)
    except Exception as e:
        print(f"Error running npm install: {e}")

    with open(package_json_path, 'r', encoding='utf-8') as f:
        pkg_data = json.load(f)
    scripts = pkg_data.get('scripts', {})
    
    release_script = None
    if 'release:dev' in scripts:
        release_script = 'release:dev'
    elif 'release' in scripts:
        release_script = 'release'
        
    if release_script:
        print(f"Generating release version: npm run {release_script}")
        try:
            subprocess.run(['npm', 'run', release_script], cwd=repo_path, check=True)
            print("Release built successfully!")
        except Exception as e:
            print(f"Error building release: {e}")

    # Recursive clean of node_modules and dist from destination folder
    print("Cleaning build artifacts from source folder...")
    for root, dirs, files in os.walk(repo_path, topdown=False):
        for d in dirs:
            if d in ('node_modules', 'dist'):
                dir_path = os.path.join(root, d)
                shutil.rmtree(dir_path, ignore_errors=True)

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python convert.py <src_path> <dest_path>")
        sys.exit(1)
    convert_extension(sys.argv[1], sys.argv[2])
