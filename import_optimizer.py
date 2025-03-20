#!/usr/bin/env python3
"""
Import Optimizer Script

This script analyzes Python files in a project and optimizes imports by:
1. Removing unused imports
2. Organizing imports into standard library, third-party, and local groups
3. Sorting imports alphabetically within each group
4. Removing duplicate imports

Usage:
    python import_optimizer.py [--check] [--fix] [path]

Arguments:
    --check     Check for import issues without fixing them
    --fix       Fix import issues (default is to only report issues)
    path        Path to directory or file to analyze (default: current directory)
"""

import os
import sys
import ast
import re
import importlib
import argparse
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional, Any

# Standard library modules
STDLIB_MODULES = set(sys.builtin_module_names)
# Add other standard library modules
for module_name in sys.modules:
    if not module_name.startswith('_') and '.' not in module_name:
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, '__file__') and module.__file__:
                if module.__file__.startswith(sys.prefix) and 'site-packages' not in module.__file__:
                    STDLIB_MODULES.add(module_name)
        except (ImportError, AttributeError):
            pass

class ImportVisitor(ast.NodeVisitor):
    """AST visitor that collects import statements and their usage"""
    
    def __init__(self):
        self.imports = {}  # name -> (module, alias, lineno)
        self.from_imports = {}  # (module, name) -> (alias, lineno)
        self.used_names = set()
        
    def visit_Import(self, node):
        """Visit Import nodes"""
        for name in node.names:
            self.imports[name.asname or name.name] = (name.name, name.asname, node.lineno)
        self.generic_visit(node)
        
    def visit_ImportFrom(self, node):
        """Visit ImportFrom nodes"""
        for name in node.names:
            if name.name == '*':
                # Wildcard imports are problematic for static analysis
                # We'll flag them separately
                continue
            self.from_imports[(node.module, name.name)] = (name.asname, node.lineno)
        self.generic_visit(node)
        
    def visit_Name(self, node):
        """Visit Name nodes to track usage"""
        if isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)
        self.generic_visit(node)
        
    def visit_Attribute(self, node):
        """Visit Attribute nodes to track usage"""
        if isinstance(node.value, ast.Name):
            # For attributes like module.attribute, we track the module name
            self.used_names.add(node.value.id)
        self.generic_visit(node)

def parse_file(file_path: str) -> Tuple[ast.Module, str]:
    """Parse a Python file and return the AST and source code"""
    with open(file_path, 'r', encoding='utf-8') as f:
        source = f.read()
    return ast.parse(source), source

def analyze_imports(file_path: str) -> Dict[str, Any]:
    """Analyze imports in a Python file"""
    try:
        tree, source = parse_file(file_path)
    except (SyntaxError, UnicodeDecodeError) as e:
        return {
            'error': f"Error parsing {file_path}: {str(e)}",
            'unused_imports': [],
            'wildcard_imports': [],
            'duplicate_imports': [],
            'unorganized_imports': False
        }
    
    # Find all imports and their usage
    visitor = ImportVisitor()
    visitor.visit(tree)
    
    # Find unused imports
    unused_imports = []
    for name, (module, alias, lineno) in visitor.imports.items():
        if name not in visitor.used_names:
            unused_imports.append((name, module, lineno))
    
    for (module, name), (alias, lineno) in visitor.from_imports.items():
        imported_name = alias or name
        if imported_name not in visitor.used_names:
            unused_imports.append((imported_name, f"{module}.{name}", lineno))
    
    # Find wildcard imports
    wildcard_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(n.name == '*' for n in node.names):
            wildcard_imports.append((node.module, node.lineno))
    
    # Find duplicate imports
    seen_imports = {}
    duplicate_imports = []
    
    for name, (module, alias, lineno) in visitor.imports.items():
        if module in seen_imports:
            duplicate_imports.append((module, lineno))
        else:
            seen_imports[module] = lineno
    
    for (module, name), (alias, lineno) in visitor.from_imports.items():
        key = f"{module}.{name}"
        if key in seen_imports:
            duplicate_imports.append((key, lineno))
        else:
            seen_imports[key] = lineno
    
    # Check if imports are organized
    import_lines = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_lines.append(node.lineno)
    
    # Imports should be at the top of the file and grouped together
    unorganized_imports = False
    if import_lines:
        # Check if imports are not at the top (allowing for docstrings and comments)
        if min(import_lines) > 10:  # Arbitrary threshold
            unorganized_imports = True
        
        # Check if imports are not grouped together
        if max(import_lines) - min(import_lines) > len(import_lines) + 5:  # Allow for some spacing
            unorganized_imports = True
    
    return {
        'unused_imports': unused_imports,
        'wildcard_imports': wildcard_imports,
        'duplicate_imports': duplicate_imports,
        'unorganized_imports': unorganized_imports
    }

def fix_imports(file_path: str) -> bool:
    """Fix import issues in a Python file"""
    try:
        tree, source = parse_file(file_path)
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"Error parsing {file_path}: {str(e)}")
        return False
    
    # Get all import nodes
    import_nodes = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_nodes.append(node)
    
    if not import_nodes:
        return False  # No imports to fix
    
    # Extract import statements
    import_statements = []
    for node in import_nodes:
        start_line = node.lineno - 1
        end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line
        
        # Get the import statement text
        statement_lines = source.splitlines()[start_line:end_line+1]
        statement = '\n'.join(statement_lines)
        
        if isinstance(node, ast.Import):
            modules = [name.name for name in node.names]
            aliases = {name.name: name.asname for name in node.names if name.asname}
            import_statements.append({
                'type': 'import',
                'modules': modules,
                'aliases': aliases,
                'statement': statement,
                'lineno': start_line,
                'end_lineno': end_line
            })
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:  # relative import
                continue
            names = [name.name for name in node.names]
            aliases = {name.name: name.asname for name in node.names if name.asname}
            import_statements.append({
                'type': 'from',
                'module': node.module,
                'names': names,
                'aliases': aliases,
                'statement': statement,
                'lineno': start_line,
                'end_lineno': end_line,
                'level': node.level  # For relative imports
            })
    
    # Find unused imports
    visitor = ImportVisitor()
    visitor.visit(tree)
    
    unused_names = set()
    for name, (module, alias, lineno) in visitor.imports.items():
        if name not in visitor.used_names:
            unused_names.add(name)
    
    for (module, name), (alias, lineno) in visitor.from_imports.items():
        imported_name = alias or name
        if imported_name not in visitor.used_names:
            unused_names.add(imported_name)
    
    # Organize imports into groups
    stdlib_imports = []
    third_party_imports = []
    local_imports = []
    
    for stmt in import_statements:
        if stmt['type'] == 'import':
            modules = stmt['modules']
            if all(module.split('.')[0] in STDLIB_MODULES for module in modules):
                stdlib_imports.append(stmt)
            elif any(module.startswith(('frontend', 'backend')) for module in modules):
                local_imports.append(stmt)
            else:
                third_party_imports.append(stmt)
        else:  # from import
            module = stmt['module']
            if module.split('.')[0] in STDLIB_MODULES:
                stdlib_imports.append(stmt)
            elif module.startswith(('frontend', 'backend')):
                local_imports.append(stmt)
            else:
                third_party_imports.append(stmt)
    
    # Sort imports within each group
    def sort_key(stmt):
        if stmt['type'] == 'import':
            return stmt['modules'][0].lower()
        else:
            return stmt['module'].lower()
    
    stdlib_imports.sort(key=sort_key)
    third_party_imports.sort(key=sort_key)
    local_imports.sort(key=sort_key)
    
    # Generate new import statements
    new_imports = []
    
    # Helper to generate import statement
    def generate_import(stmt):
        if stmt['type'] == 'import':
            modules = [m for m in stmt['modules'] if m not in unused_names]
            if not modules:
                return None
            
            parts = []
            for module in modules:
                if module in stmt['aliases'] and stmt['aliases'][module]:
                    parts.append(f"{module} as {stmt['aliases'][module]}")
                else:
                    parts.append(module)
            
            return f"import {', '.join(parts)}"
        else:  # from import
            names = [n for n in stmt['names'] if n not in unused_names and (stmt['aliases'].get(n) or n) not in unused_names]
            if not names:
                return None
            
            parts = []
            for name in names:
                if name in stmt['aliases'] and stmt['aliases'][name]:
                    parts.append(f"{name} as {stmt['aliases'][name]}")
                else:
                    parts.append(name)
            
            level_prefix = '.' * stmt['level'] if 'level' in stmt else ''
            return f"from {level_prefix}{stmt['module']} import {', '.join(parts)}"
    
    # Add imports from each group
    for group in [stdlib_imports, third_party_imports, local_imports]:
        if group:
            for stmt in group:
                import_stmt = generate_import(stmt)
                if import_stmt:
                    new_imports.append(import_stmt)
            new_imports.append('')  # Add blank line between groups
    
    if new_imports and new_imports[-1] == '':
        new_imports.pop()  # Remove trailing blank line
    
    # Find the insertion point for imports
    # Look for module docstring or shebang
    lines = source.splitlines()
    insert_line = 0
    
    # Skip shebang line if present
    if lines and lines[0].startswith('#!'):
        insert_line = 1
    
    # Skip module docstring if present
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Str):
            if node.lineno == 1 or (insert_line == 1 and node.lineno == 2):
                insert_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
                break
    
    # Create the new file content
    new_content = []
    new_content.extend(lines[:insert_line])
    new_content.append('')  # Blank line after docstring/shebang
    new_content.extend(new_imports)
    new_content.append('')  # Blank line after imports
    
    # Find the first non-import statement
    first_non_import = float('inf')
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom, ast.Expr)) or \
           (isinstance(node, ast.Expr) and not isinstance(node.value, ast.Str)):
            first_non_import = min(first_non_import, node.lineno - 1)
    
    if first_non_import < float('inf'):
        # Add the rest of the file after the imports
        new_content.extend(lines[first_non_import:])
    
    # Write the new content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_content))
    
    return True

def process_file(file_path: str, fix: bool = False) -> Dict[str, Any]:
    """Process a single Python file"""
    if not file_path.endswith('.py'):
        return None
    
    result = analyze_imports(file_path)
    result['file_path'] = file_path
    
    if fix and (result.get('unused_imports') or result.get('duplicate_imports') or result.get('unorganized_imports')):
        success = fix_imports(file_path)
        result['fixed'] = success
    
    return result

def process_directory(directory: str, fix: bool = False) -> List[Dict[str, Any]]:
    """Process all Python files in a directory recursively"""
    results = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                result = process_file(file_path, fix)
                if result:
                    results.append(result)
    return results

def print_results(results: List[Dict[str, Any]]) -> None:
    """Print analysis results"""
    issues_found = False
    
    for result in results:
        file_issues = False
        file_path = result['file_path']
        
        if 'error' in result:
            print(f"\n{file_path}:")
            print(f"  Error: {result['error']}")
            issues_found = True
            continue
        
        if result.get('unused_imports'):
            if not file_issues:
                print(f"\n{file_path}:")
                file_issues = True
            
            print("  Unused imports:")
            for name, module, lineno in result['unused_imports']:
                print(f"    Line {lineno}: {name} from {module}")
            issues_found = True
        
        if result.get('wildcard_imports'):
            if not file_issues:
                print(f"\n{file_path}:")
                file_issues = True
            
            print("  Wildcard imports:")
            for module, lineno in result['wildcard_imports']:
                print(f"    Line {lineno}: from {module} import *")
            issues_found = True
        
        if result.get('duplicate_imports'):
            if not file_issues:
                print(f"\n{file_path}:")
                file_issues = True
            
            print("  Duplicate imports:")
            for module, lineno in result['duplicate_imports']:
                print(f"    Line {lineno}: {module}")
            issues_found = True
        
        if result.get('unorganized_imports'):
            if not file_issues:
                print(f"\n{file_path}:")
                file_issues = True
            
            print("  Imports are not properly organized")
            issues_found = True
        
        if result.get('fixed'):
            print("  ✓ Fixed import issues")
    
    if not issues_found:
        print("No import issues found.")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Analyze and fix import issues in Python files')
    parser.add_argument('--check', action='store_true', help='Check for import issues without fixing them')
    parser.add_argument('--fix', action='store_true', help='Fix import issues')
    parser.add_argument('path', nargs='?', default='.', help='Path to directory or file to analyze')
    
    args = parser.parse_args()
    
    if os.path.isfile(args.path):
        results = [process_file(args.path, fix=args.fix and not args.check)]
    else:
        results = process_directory(args.path, fix=args.fix and not args.check)
    
    print_results(results)

if __name__ == '__main__':
    main()
