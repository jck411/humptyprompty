# Git Commands Summary

## Viewing and Managing Commits:
1. **`git log`** – Shows commit history to find specific commit hashes.
2. **`git status`** – Displays the current state of the working directory and staging area.

## Resetting to a Previous State:
3. **`git reset --hard <commit-hash>`** – Reverts the repository to a specific commit, discarding all changes in tracked files.
4. **`git reset --hard HEAD`** – Resets the working directory to the latest commit, discarding all uncommitted changes.
5. **`git reset --hard origin/raspi2`** – Resets your local branch to exactly match the remote branch.

## Cleaning Untracked Files:
6. **`git clean -df`** – Removes untracked files and directories.
7. **`git clean -n`** – Performs a dry run to show what would be deleted.

## Syncing with Remote:
8. **`git fetch`** – Fetches changes from a remote repository without merging them.
9. **`git pull`** – Fetches and merges updates from the remote branch into the current branch.

## Overwriting Remote with Local:
10. **`git push origin <branch-name> --force`** – Overwrites the remote branch with your local branch (use carefully).
