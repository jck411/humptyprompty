
run from root:

python -m backend.main


#  Git Commands Cheat Sheet

## 🟢 Setting Up Git
| Action | Command |
|--------|---------|
| Set global username | `git config --global user.name "Your Name"` |
| Set global email | `git config --global user.email "you@example.com"` |
| Check Git config | `git config --list` |
| Initialize a repository | `git init` |
| Clone a repository | `git clone <repo-url>` |

---

## 🟡 Checking the Repository Status
| Action | Command |
|--------|---------|
| Check current status | `git status` |
| Show commit history | `git log` |
| Show commit history (one line per commit) | `git log --oneline --graph --all` |
| Show last commit changes | `git show` |
| Check what has changed before staging | `git diff` |

---

## 🟠 Staging & Committing
| Action | Command |
|--------|---------|
| Stage all changes | `git add .` |
| Stage a specific file | `git add <file>` |
| Unstage a file | `git reset HEAD <file>` |
| Commit staged changes | `git commit -m "commit message"` |
| Commit all modified/deleted files (skip `git add`) | `git commit -a -m "commit message"` |

---

## 🔵 Working with Branches
| Action | Command |
|--------|---------|
| List all branches | `git branch` |
| Create a new branch | `git branch <branch-name>` |
| Switch to a branch | `git checkout <branch-name>` (old) / `git switch <branch-name>` (new) |
| Create & switch to a new branch | `git checkout -b <branch-name>` / `git switch -c <branch-name>` |
| Delete a branch (local) | `git branch -d <branch-name>` |
| Delete a branch (force delete) | `git branch -D <branch-name>` |

---

## 🟣 Merging & Rebasing
| Action | Command |
|--------|---------|
| Merge a branch into the current branch | `git merge <branch-name>` |
| Abort a merge if there's a conflict | `git merge --abort` |
| Rebase a branch (replay commits from another branch on top) | `git rebase <branch-name>` |
| Continue rebase after conflict resolution | `git rebase --continue` |
| Skip a commit during rebase | `git rebase --skip` |

---

## 🟤 Pushing & Pulling
| Action | Command |
|--------|---------|
| Fetch latest changes from remote (without merging) | `git fetch` |
| Fetch & merge remote changes | `git pull` |
| Push local commits to remote repo | `git push` |
| Push and set upstream branch | `git push --set-upstream origin <branch-name>` |
| Force push (overwrite remote history - use with caution!) | `git push --force` |

---

## ⚫ Undoing Changes & Fixing Mistakes
| Action | Command |
|--------|---------|
| Undo local changes (before staging) | `git checkout -- <file>` |
| Undo staged changes (before commit) | `git reset HEAD <file>` |
| Undo the last commit (keep changes unstaged) | `git reset --soft HEAD~1` |
| Undo the last commit (discard changes completely!) | `git reset --hard HEAD~1` |
| Revert a commit (safe method to undo changes in history) | `git revert <commit-hash>` |
| Delete all uncommitted changes (hard reset) | `git reset --hard` |

---

## 🟢 Working with Remote Repositories
| Action | Command |
|--------|---------|
| Add a remote repository | `git remote add origin <repo-url>` |
| Show remote repositories | `git remote -v` |
| Change remote URL | `git remote set-url origin <new-url>` |
| Remove a remote repository | `git remote remove origin` |

---

## 🟡 Stashing Changes
| Action | Command |
|--------|---------|
| Stash current changes | `git stash` |
| List stashed changes | `git stash list` |
| Apply the last stashed changes | `git stash apply` |
| Apply and delete the last stash | `git stash pop` |
| Drop a specific stash | `git stash drop <stash@{n}>` |

---

## 🔥 Cleaning Untracked Files
| Action | Command |
|--------|---------|
| Remove untracked files | `git clean -f` |
| Remove untracked files & directories | `git clean -fd` |
| Remove untracked & ignored files | `git clean -fx` |
| Remove everything (untracked, ignored, directories) | `git clean -fxd` |
| Show what would be deleted (preview) | `git clean -n` |

---

## 🚀 Bonus: Git Shortcuts
| Action | Command |
|--------|---------|
| View a simple commit log | `git log --oneline --graph --decorate --all` |
| View detailed changes for a file | `git blame <file>` |
| Show which commit modified a line in a file | `git log -p -L <line-number>,<line-number>:<file>` |

---

## 💡 Common Workflows
### 🌱 Start a New Project
```sh
git init
git add .
git commit -m "Initial commit"
git remote add origin <repo-url>
git push -u origin main
