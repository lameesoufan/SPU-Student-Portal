# Git Branch Commands Guide

## Getting a Remote Branch

### Method 1: Fetch and Checkout (Recommended)
```bash
git fetch origin
git checkout feature/projects-service-updates
```

### Method 2: Fetch Specific Branch
```bash
git fetch origin feature/projects-service-updates:feature/projects-service-updates
git checkout feature/projects-service-updates
```

### Method 3: Checkout with Tracking
```bash
git fetch origin
git checkout -b feature/projects-service-updates origin/feature/projects-service-updates
```

---

## Pushing Your Branch to Remote

### First Time Push (Set Upstream)
```bash
git push -u origin feature/projects-service-updates
```

### Subsequent Pushes
```bash
git push
```

---

## Common Branch Operations

### List All Branches
```bash
# Local branches
git branch

# Remote branches
git branch -r

# All branches (local and remote)
git branch -a
```

### Check Current Branch
```bash
git branch --show-current
```

### Create a New Branch
```bash
# Create and switch to new branch
git checkout -b branch-name

# Or using newer syntax
git switch -c branch-name
```

### Switch Between Branches
```bash
# Using checkout
git checkout branch-name

# Using switch (Git 2.23+)
git switch branch-name
```

### Delete a Branch
```bash
# Delete local branch (safe - prevents deletion if unmerged)
git branch -d branch-name

# Force delete local branch
git branch -D branch-name

# Delete remote branch
git push origin --delete branch-name
```

### Update Your Branch with Latest Changes
```bash
# Pull latest changes from remote
git pull

# Or fetch and merge separately
git fetch origin
git merge origin/feature/projects-service-updates
```

### Sync with Main Branch
```bash
# Switch to main and update
git checkout main
git pull origin main

# Switch back to your branch
git checkout feature/projects-service-updates

# Merge main into your branch
git merge main

# Or rebase your branch on main
git rebase main
```

---

## Working with the Current Branch

### Check Branch Status
```bash
git status
```

### See Branch History
```bash
git log --oneline --graph --decorate
```

### Compare Branches
```bash
# See differences between branches
git diff main..feature/projects-service-updates

# See commits in feature branch not in main
git log main..feature/projects-service-updates
```

---

## Troubleshooting

### Branch Not Found After Fetch
```bash
# Make sure you've fetched the latest
git fetch origin

# Verify remote branches exist
git branch -r

# Try explicit checkout
git checkout -b feature/projects-service-updates origin/feature/projects-service-updates
```

### Update Remote Branch List
```bash
# Prune deleted remote branches
git fetch --prune
```

### Discard Local Changes
```bash
# Discard all local changes
git reset --hard HEAD

# Discard specific file
git checkout -- filename
```

---

## Best Practices

1. **Always fetch before starting work**
   ```bash
   git fetch origin
   ```

2. **Keep your branch updated with main**
   ```bash
   git checkout main
   git pull
   git checkout feature/projects-service-updates
   git merge main
   ```

3. **Use descriptive branch names**
   - `feature/` for new features
   - `bugfix/` for bug fixes
   - `hotfix/` for urgent fixes
   - `refactor/` for code refactoring

4. **Commit often with clear messages**
   ```bash
   git add .
   git commit -m "Clear description of changes"
   ```

5. **Push regularly to backup your work**
   ```bash
   git push
   ```

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `git fetch origin` | Get latest branches and changes from remote |
| `git checkout branch-name` | Switch to a branch |
| `git checkout -b new-branch` | Create and switch to new branch |
| `git push -u origin branch-name` | Push and set upstream tracking |
| `git pull` | Fetch and merge changes from remote |
| `git branch` | List local branches |
| `git branch -r` | List remote branches |
| `git status` | Check current branch status |
| `git merge branch-name` | Merge another branch into current |

---

**Note:** Replace `feature/projects-service-updates` with your actual branch name in the commands above.
