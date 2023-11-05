import sys
import os
import utils
from index import Index, IndexEntry
from log import Log
from commit import Commit
from tree import Tree, Blob
from argparser import GitArgParser
from diff import CommitDiff, DiffTraceAction
from gitpath import GitPath
from functools import reduce
from reflog import Reflog
from merge import ThreeWayMerge, SimpleThreeWayMerge
import glob


def abort(err):
    print(err)
    exit(1)

def rev_parse(args, prnt=True):
    full_rev = args.rev

    symbolic_rev_files = ["HEAD", "ORIG_HEAD", "MERGE_HEAD"]
    result = None
    ambigious = False

    parts = full_rev.split("~")
    rev = parts[0]
    # TODO: is branch~2 same as branch~1~1? if so, shouldn't reduce here
    num_parents_back = reduce(lambda x,y: x + y, map(lambda x : int(x) if x != '' else 1, parts[1:])) if len(parts) > 1 else 0

    if utils.is_valid_hash(rev):
        result = rev
    elif rev in symbolic_rev_files:
        file = os.path.join(".git", rev)
        if os.path.exists(file):
            with open(file, "r") as f:
                content = f.read().strip()
                if content.startswith("ref: "):
                    ref = content.split("ref: ")[1]
                    (result, ambigious) = utils.commit_hash_from_ref(ref)
                elif utils.is_valid_hash(content):
                    result = content   
    else:        
        (result, ambigious) = utils.commit_hash_from_ref(rev)


    def fail():
        print(full_rev)
        abort(f"fatal: ambiguous argument '{full_rev}': unknown revision or path not in the working tree.")
        # print("Use '--' to separate paths from revisions, like this:")
        # print("'git <command> [<revision>...] -- [<file>...]'")
    
    if result is not None:
        commit = Commit.FromHash(result)
        for _ in range(num_parents_back):
            result = commit.getParentHash()
            if result is None:
                fail()
            commit = Commit.FromHash(result)

    
    if prnt:
        if result is None:
            fail()
        else:
            if ambigious:
                print(f"warning: refname '{rev}' is ambiguous.")
            print(result)

    return result

def stash(args, prnt=True):
    command = args.command

    if command is None:
        pass
    elif command == 'pop':
        pass

    abort('unimplemented')


def diff(args, prnt=True):
    rev1 = args.rev1
    rev2 = args.rev2

    commit_diff = None
    if rev1 is None and rev2 is None:
        # Compare the working dir against the current index
        tree1 = Tree.FromHash(write_tree(prnt=False))
        tree2 = Tree.FromWorkingDir()
        commit_diff = CommitDiff(tree1, tree2)
    else:
        # TODO: there are other cases
        rev1_hash = GitArgParser.Execute(f"rev-parse {rev1}", prnt=False)
        rev2_hash = GitArgParser.Execute(f"rev-parse {rev2}", prnt=False)
        tree1, tree2 = Commit.FromHash(rev1_hash).getTree(), Commit.FromHash(rev2_hash).getTree()
        commit_diff = CommitDiff(tree1, tree2)

    if commit_diff is not None and prnt:
        commit_diff.print()

    return commit_diff


# returns the hash of the merge base given two revisions
def merge_base(args, prnt=True):
    rev1 = args.rev1
    rev2 = args.rev2

    rev1_hash = GitArgParser.Execute(f"rev-parse {rev1}", prnt=False)
    rev2_hash = GitArgParser.Execute(f"rev-parse {rev2}", prnt=False)

    rev1_reachable_commits = Commit.FromHash(rev1_hash).reachableCommits()
    rev2_reachable_commits = Commit.FromHash(rev2_hash).reachableCommits()

    common_ancestors = set(rev1_reachable_commits).intersection(set(rev2_reachable_commits))
    if len(common_ancestors) > 0:
        most_recent_common_ancestor = sorted(list(common_ancestors), key=lambda commit: commit.commitDateTime(), reverse=True)[0].sha1
        if prnt:
            print(most_recent_common_ancestor)
        return most_recent_common_ancestor
    return None
    
def rebase(args, prnt=True):
    merge_source_rev = args.rev
    target_branch_name = utils.current_branch()

    merge_source_hash = GitArgParser.Execute(f"rev-parse {merge_source_rev}", prnt=False)
    merge_target_hash = GitArgParser.Execute(f"rev-parse {target_branch_name}", prnt=False)

    # If the commit hashes of the source and destination are the same, nothing to do
    if merge_source_hash == merge_target_hash:
        print("Already up to date.")
        return

    # Checkout a new branch based on the branch we are rebasing onto
    temp_branch_name = "REBASE"
    GitArgParser.Execute(f"checkout -b {temp_branch_name} {merge_source_rev}", prnt=False)

    # find the merge base
    merge_base_hash = GitArgParser.Execute(f"merge-base {args.branch_name} {target_branch_name}", prnt=False)

    #TODO: need a similar check for the merge base here that we have in merge()

    # find all commits that need to be cherry-picked onto the rebase branch
    current_commit = Commit.FromHash(merge_target_hash)
    commits_to_cherry_pick = [current_commit]
    while current_commit.getParentHash() != merge_base_hash:
        current_commit = Commit.FromHash(current_commit.getParentHash())
        commits_to_cherry_pick.append(current_commit)

    # current_commit now stores the commit to be cherry-picked
    # cherry-pick each commit onto the rebase branch
    for commit in reversed(commits_to_cherry_pick):
        successful = GitArgParser.Execute(f"cherry-pick {commit.getCommitHash()}", prnt=False)
        # TODO: if not successful, ask user to resolve conflicts

    GitArgParser.Execute(f"branch --force {target_branch_name}", prnt=False)
    GitArgParser.Execute(f"checkout {target_branch_name}", prnt=False)
    GitArgParser.Execute(f"branch -d {temp_branch_name}", prnt=False) #TODO: should use -D

def cherry_pick(args, prnt=True):
    commit_rev = args.commit_rev
    commit_hash = GitArgParser.Execute(f"rev-parse {commit_rev}", prnt=False)
    parents = Commit.FromHash(commit_hash).parents

    if len(parents) > 1 and args.m is None:
        print(f"error: commit {commit_hash} is a merge but no -m option was given.")
        abort("fatal: cherry-pick failed")

    parent_index = args.m - 1 if args.m is not None else 0
    if parent_index >= len(parents):
        print(f"error: commit {commit_hash} does not have parent {parent_index + 1}")
        abort("fatal: cherry-pick failed")
    
    parent_commit_hash = parents[parent_index]
    commit_diff = GitArgParser.Execute(f"diff {parent_commit_hash} {commit_hash}", prnt=False)

    # file_diffs = commit_diff.getFileDiffs()
    for file_diff in commit_diff.getFileDiffs():
        filepath = file_diff.base_filepath # TODO: handle renames, deletions, etc
        for trace in file_diff.trace:
            if trace == DiffTraceAction.ADD:
                # TODO: finish...how do we do this???
                pass
    
    
    abort('unimplemented')

    with open(GitPath.Path(GitPath.CHERRY_PICK_HEAD), "w") as f:
        f.write(commit_hash)

    return True # TODO: return False if there are conflicts that need to be resolved

def merge(args, prnt=True):
    merge_source_rev = args.rev
    target_branch_name = utils.current_branch()

    merge_source_hash = GitArgParser.Execute(f"rev-parse {merge_source_rev}", prnt=False)
    merge_target_hash = GitArgParser.Execute(f"rev-parse {target_branch_name}", prnt=False)

    # If the commit hashes of the source and destination are the same, nothing to do
    if merge_source_hash == merge_target_hash:
        print("Already up to date.")
        return

    # source_reachable_commits = Commit.FromHash(merge_source_hash).reachableCommits()
    # current_branch_reachable_commits = Commit.FromHash(current_branch_hash).reachableCommits()

    # find the merge base
    merge_base_hash = GitArgParser.Execute(f"merge-base {merge_source_rev} {target_branch_name}", prnt=False)

    # TODO: is this the only condition? what if merge_base_hash is in the history of current branch?
    # maybe gets more complicated with 
    if merge_base_hash == merge_target_hash:
        # This is a fast forward, just update current branch's head pointer
        print(f"Updating {utils.shortened_hash(merge_target_hash)}..{utils.shortened_hash(merge_source_hash)}")
        print("Fast-Forward")

        commit_diff = GitArgParser.Execute(f"diff {merge_base_hash} {merge_source_hash}", prnt=False)
        commit_diff.printVisualSummary()
        commit_diff.printNumericalSummary()
        commit_diff.printExistenceChanges()

        # update the files (for a fast-forward this is easy)
        utils.update_files_to_commit_hash(merge_source_hash)
        GitArgParser.Execute(f"update-ref refs/heads/{target_branch_name} {merge_source_hash}")

    else:
        # 3-way merge
        twmerge = SimpleThreeWayMerge(merge_base_hash, merge_source_rev, merge_source_hash, merge_target_hash)
        twmerge.merge()


def commit(args, prnt=True):
    is_merge = os.path.exists(GitPath.Path(GitPath.MERGE_MODE))

    if args.m is None and not is_merge:
        abort("fatal: must supply a message using -m")

    merge_msg = utils.read_merge_msg()
    message = " ".join(args.m) if args.m is not None else merge_msg

    # TODO: if HEAD is detached, this won't work
    current_branch = utils.current_branch()
    if current_branch is None:
        abort("fatal: not on a branch")
    
    parent_commit = None
    ref_file = GitPath.BranchPath(current_branch)
    if os.path.exists(ref_file):
        with open(ref_file, "r") as f:
            parent_commit = f.read().strip()
    
    merge_parent_commit = None
    if is_merge:
        merge_head_file = GitPath.Path(GitPath.MERGE_HEAD)
        if os.path.exists(merge_head_file):
            with open(merge_head_file) as f:
                merge_parent_commit = f.read().strip()

    tree_hash = GitArgParser.Execute("write-tree", prnt=False)

    signature = utils.signature() # TODO: is author ever different?
    commit_file_content = f'tree {tree_hash}\n{"parent " + parent_commit if parent_commit else ""}\n{"parent " + merge_parent_commit if merge_parent_commit else ""}\nauthor {signature}\ncommitter {signature}\n\n{message}\n'
    commit_file_header = f'commit {len(commit_file_content)}\0'
    commit_hash = utils.write_object_file((commit_file_header + commit_file_content).encode('utf-8'))
    
    if prnt:
        print(f"[{current_branch}{' (root-commit)' if parent_commit is None else ''} {utils.shortened_hash(commit_hash)}] {message}")

    if parent_commit is not None:
        # TODO: handle the case where there is no parent commit yet, or if there are two parents
        commit_diff = GitArgParser.Execute(f"diff {parent_commit} {commit_hash}", prnt=False)
        if prnt:
            commit_diff.printNumericalSummary()
            commit_diff.printExistenceChanges()

    #update refs/heads/{current_branch} with hash of file
    with open(ref_file, "w") as f:
        f.write(commit_hash)

    # cleanup merge housekeeping if there was any
    if is_merge:
        os.remove(GitPath.Path(GitPath.MERGE_MODE))
        os.remove(GitPath.Path(GitPath.MERGE_MSG))
        os.remove(GitPath.Path(GitPath.MERGE_HEAD))
        os.remove(GitPath.Path(GitPath.ORIG_HEAD))

    Reflog.Commit(current_branch, commit_hash, is_merge=is_merge)

def add(args, prnt=True):
    file_pattern = args.file_pattern
    # TODO: need much more robust file pattern expansion
    # TODO: doesn't work with dotfiles yet. might not want to use glob
    if os.path.isdir(file_pattern):
        file_pattern += "/**/*"
    if file_pattern.startswith("./"):
        file_pattern = file_pattern[2:]
    files = glob.glob(file_pattern, recursive=True)
    # TODO: also "add" files that have been deleted when using glob
    for filepath in files:
        if os.path.isfile(filepath) and not utils.ignored(filepath):
            # TODO: get filepath with respect to outer git dir
            # TODO: is it ok to always include --add?
            GitArgParser.Execute(f"update-index --add {'--remove' if not os.path.exists(filepath) else ''} {filepath}")

def show(args, prnt=True):
    rev = args.rev
    quiet = args.quiet

    GitArgParser.Execute(f'log {rev} -n 1')
    if not quiet:
        GitArgParser.Execute(f'diff {rev}~ {rev}')

def revert(args, prnt=True):
    rev = args.rev

    dff = GitArgParser.Execute(f'diff {rev} {rev}~', prnt=False)
    # dff.print()

    # TODO: diff should be applied to the current commit

    abort('unimplemented')

def reset(args, prnt=True):
    soft = args.soft
    mixed = args.mixed
    hard = args.hard
    rev = args.rev

    # make mixed the default if nothing else is specified
    mixed = True if not soft and not hard else mixed

    prev_hash = Commit.CurrentCommitHash()
    rev_hash = GitArgParser.Execute(f"rev-parse {rev}", prnt=False)
    commit = Commit.FromHash(rev_hash)
    
    if soft or mixed or hard:
        GitArgParser.Execute(f"update-ref refs/heads/{utils.current_branch()} {rev_hash}")

    if hard:
        utils.update_files_to_commit_hash(rev_hash)
        if prnt:
            print(f"HEAD is now at {utils.shortened_hash(commit.getCommitHash())} {commit.message}")

    if mixed or hard:
        Index.FromTree(commit.getTree()).writeToFile()

    Reflog.Reset(utils.current_branch(), prev_hash, rev_hash, rev)

def restore(args, prnt=True):
    filepath = args.file
    staged = args.staged

    if staged:
        # TODO: for some reason, after running this command, and then using the real git status, the file comes up as deleted
        GitArgParser.Execute(f"update-index --remove {filepath}")
    else:
        abort("unimplemented, gotta figure out what the behavior is here")

def rm(args, prnt=True):
    filepath = args.file

    GitArgParser.Execute(f"update-index --remove {filepath}")

    # TODO: what if filepath is a folder?
    os.remove(filepath)

def log(args, prnt=True):
    rev = args.rev

    commit_hash = None
    if rev is None:
        commit_hash = Commit.CurrentCommitHash()
        if commit_hash is None:
            print(f"fatal: your current branch '{utils.current_branch()}' does not have any commits yet")
            return
    else:
        commit_hash = GitArgParser.Execute(f"rev-parse {rev}", prnt=False)
        if commit_hash is None:
            print(f"fatal: ambiguous argument '{rev}': unknown revision or path not in the working tree.")
            return
            # print("Use '--' to separate paths from revisions, like this:")
            # print('git <command> [<revision>...] -- [<file>...]')
    commit = Commit.FromHash(commit_hash)
    commit.printLog(args)

def reflog(args, prnt=True):
    ref = args.ref

    ref_hash = GitArgParser.Execute(f'rev-parse {ref}', prnt=False)
    if ref_hash is None:
        return
    
    log_file = GitPath.Path(GitPath.HEAD_log) if ref == "HEAD" else GitPath.BranchLogPath(ref)
    if log_file is None:
        return
    
    lines = []
    with open(log_file, "r") as f:
        lines = f.readlines()

    lines.reverse()
    for i in range(len(lines)):
        line = lines[i]
        # prev_hash = line[:40]
        curr_hash = line[41:81]
        message = line.split("\t")[1]
        branch_summary = utils.branch_summary_for_commit(curr_hash)
        print(f"{utils.bcolors.WARNING}{utils.shortened_hash(curr_hash)}{utils.bcolors.ENDC}", end="")
        print(f" {branch_summary}" if len(branch_summary) > 0 else "", end="")
        print(f" {ref}@{'{'}{i}{'}'}", end="")
        print(f" {message}", end="")


def branch(args, prnt=True):
    branch_name = args.branch_name
    new_branch_base = args.new_branch_base
    delete_branch = args.d
    force = args.force

    heads_folder = GitPath.Path(GitPath.heads)

    if delete_branch:
        if branch_name is None:
            abort("fatal: branch name required")
        if utils.current_branch() == branch_name:
            abort(f"error: Cannot delete branch '{branch_name}' checked out at '{os.path.abspath(os.curdir)}'")

        ref_file = GitPath.BranchPath(branch_name)
        if not os.path.exists(ref_file):
            abort(f"fatal: branch '{branch_name}' not found.")
        
        with open(ref_file, "r") as f:
            branch_hash = f.read().strip()
            if prnt:
                print(f"Deleted branch {branch_name} (was {utils.shortened_hash(branch_hash)}).")

        os.remove(ref_file)
        Reflog.DeleteLog(branch_name)
        # TODO: could clean up intermediate folders that have become empty
        return
        

    if branch_name is None:
        # Print all branches
        for branch in utils.all_branches():
            if branch == utils.current_branch():
                print(f"* {utils.bcolors.OKGREEN}{branch}{utils.bcolors.ENDC}")
            else:
                print(f"  {branch}")
        return
    
    if force:
        GitArgParser.Execute(f"update-ref refs/heads/{branch_name} {Commit.CurrentCommitHash()}", prnt=False)
        return

    ref_file = GitPath.BranchPath(branch_name)
    slash_position = branch_name.find("/")
    if slash_position == 0:
        abort(f"fatal: '{branch_name}' is not a valid branch name")
    elif slash_position != -1:
        intermediate_dirs = "/".join(branch_name.split("/")[:-1])
        os.makedirs(os.path.join(heads_folder, intermediate_dirs), exist_ok=True)

    if os.path.exists(ref_file):
        abort(f"fatal: a branch named '{branch_name}' already exists")

    # If a base branch was specified, use it to create the new branch, otherwise use the current commit
    new_branch_commit_hash = GitArgParser.Execute(f"rev-parse {new_branch_base}", prnt=False) if new_branch_base is not None else Commit.CurrentCommitHash()

    # TODO: what to do if no commits yet?
    GitArgParser.Execute(f"update-ref refs/heads/{branch_name} {new_branch_commit_hash}")

    # Write to log
    Reflog.CreateBranch(branch_name, utils.current_branch())

def tag(args, prnt=True):
    tag_name = args.tag_name
    delete_tag = args.d
    Log.Debug(tag_name)
    abort('unimplemented, but basically the same as branch')

def checkout(args, prnt=True):
    create_new_branch = args.b
    # TODO: this doesn't need to be a branch, can be detached
    branch_name = args.branch_name
    new_branch_base = args.new_branch_base

    prev_branch = new_branch_base if new_branch_base is not None else utils.current_branch()
    prev_commit = Commit.CurrentCommitHash()
    prev_rev = prev_branch if prev_branch is not None else prev_commit

    if create_new_branch:
        GitArgParser.Execute(f"branch {branch_name} {new_branch_base if new_branch_base is not None else ''}")

    branch_ref_file = GitPath.BranchPath(branch_name)
    branch_commit = None
    with open(branch_ref_file, "r") as f:
        branch_commit = f.read().strip()

    utils.update_files_to_commit_hash(branch_commit)

    # update the HEAD ref
    HEAD_file = GitPath.Path(GitPath.HEAD)
    with open(HEAD_file, "w") as f:
        f.write(f"ref: refs/heads/{branch_name}")

    Reflog.Checkout(prev_commit, branch_commit, prev_rev, branch_name)

    if prnt:
        print(f"Switched to {'a new ' if create_new_branch else ''}branch '{branch_name}'")

    
def update_ref(args, prnt=True):
    refname = args.refname
    new_val = args.new_val

    newval_hash = GitArgParser.Execute(f'rev-parse {new_val}', prnt=False)
    (ref_file, ambiguous) = utils.file_from_ref(refname, noexist_ok=True)

    # TODO: print ambiguous warning?
    with open(ref_file, "w") as f:
        f.write(newval_hash)

# content_override provides a way to provide custom content without needing a file or stdin
def hash_object(args, prnt=True, content_override=None):
    write = args.w
    stdin = args.stdin
    filename = args.filename
    if not stdin and filename is None and content_override is None:
        return

    object_string = ""
    if content_override is not None:
        object_string = content_override
    elif stdin:
        object_string = sys.stdin.read()
    else:
        with open(filename, "r") as f:
            object_string = f.read()
    
    # hash the object
    db_object = f"blob {len(object_string)}\0{object_string}"
    db_object_encoded = db_object.encode('utf-8')
    sha1_hash = utils.sha1hash(db_object_encoded)
    if prnt:
        print(sha1_hash)

    if write:
        utils.write_object_file(db_object_encoded)

    return sha1_hash

def write_tree(arg, prnt=True):
    index = Index.FromFile()
    tree_hash = utils.create_tree(index)
    if prnt:
        print(tree_hash)
    return tree_hash

def cat_file(args, prnt=True):
    prnt = args.p
    tpe = args.t
    object_hash = args.object_hash

    if prnt and tpe:
        abort("error: switch 'p' is incompatible with -t")

    if not prnt and not tpe:
        abort("error: need either -p or -t")

    # get file
    object_decompressed = utils.read_object_file(object_hash)
    object_decoded = object_decompressed.decode('utf-8', 'replace')
    
    # Log.Debug(object_decompressed)

    object_type = object_decoded.split(" ")[0]
    if tpe:
        print(object_type)
    elif prnt:
        # print the file's contents based on its object type
        if object_type == "blob":
            blob = Blob.FromHash(object_hash)
            blob.print()
        elif object_type == "tree":
            tree = Tree.FromHash(object_hash)
            tree.print()
        elif object_type == "commit":
            content = object_decompressed.split(b"\x00")[1]
            print(content.decode('utf-8'), end="")

def read_index(args, prnt=True):
    index = Index.FromFile()
    index.print()

def update_index(args, prnt=True):
    index = Index.FromFile()
    # Log.Debug("Index before update: ")
    # index.print()
    
    if args.cacheinfo:
        abort("cacheinfo path unimplemented")
        filemode = args.arg1
        object_hash = args.arg2
        filepath = args.arg3
        if object_hash is None or filepath is None:
            abort("must supply object_hash and filename") # TODO: what if not using --add?
    else:
        filepath = args.arg1

        if not os.path.exists(filepath) and not args.remove:
            abort(f"error: {filepath} does not exist and --remove not passed")

        if not args.add and not index.containsEntryWithFilepath(filepath):
            abort(f"index does not yet contain {filepath}, must use --add")

        if args.remove:
            index.removeEntryWithFilepath(filepath)
        else:
            object_hash = GitArgParser.Execute(f"hash-object -w {filepath}", prnt=False)

            newEntry = IndexEntry.FromFile(filepath, object_hash)
            index.addEntry(newEntry)

    index.writeToFile()
    # Log.Debug("Index after update: ")
    # index.print()

def ls_files(args, prnt=True):
    stage = args.s
    abbrev = args.abbrev

    index = Index.FromFile()
    for entry in index.entries:
        filepath = entry.getFilepathStr()
        if stage:
            sha1 = entry.getSha1Str()
            if abbrev:
                sha1 = utils.shortened_hash(sha1)
            print(f"{entry.getModeStr()} {sha1} {entry.getStageInt()}        {filepath}")
        else:
            print(filepath)
        
    
def status(args, prnt=True):
    # Get the name of the current branch (HEAD)
    branch_name = utils.current_branch()
    if branch_name is None:
        abort("not on a branch")
    print(f"On branch {branch_name}")

    # See if there have been commits yet
    ref_file = GitPath.BranchPath(branch_name)
    if not os.path.exists(ref_file):
        print("\nNo commits yet\n")

    index = Index.FromFile()

    all_files = utils.files_in_current_dir()

    current_commit_hash = Commit.CurrentCommitHash()
    current_commit = Commit.FromHash(current_commit_hash)

    untracked_files = []
    unstaged_changes = []
    staged_changes = []

    for file in all_files:
        index_entry = index.getEntryWithFilepath(file)
        if index_entry is None:
            untracked_files.append(file)

    for entry in index.entries:
        filepath = entry.getFilepathStr()

        if current_commit is None:
            # There are no commits yet
            staged_changes.append(f"new file:   {filepath}")
        else:
            current_tree = current_commit.getTree()
            current_tree_files = current_tree.getFiles()
            if filepath not in current_tree_files:
                # The current commit's tree does not contain this file
                staged_changes.append(f"new file:   {filepath}")

        if not os.path.exists(filepath):
            unstaged_changes.append(f"deleted:    {filepath}")
            continue

        entry_mtime = entry.getMTime()
        stat = os.stat(filepath)
        file_mtime = stat.st_mtime
        # Log.Debug(f"times for {filepath}:: real: {file_mtime}, stored: {entry_mtime}")
        if file_mtime > entry_mtime + 0.01: # TODO: remove this epsilon once nanoseconds are more exact
            unstaged_changes.append(f"modified:   {filepath}")

        if current_commit is not None:
            current_tree = current_commit.getTree()
            current_tree_files = current_tree.getFiles()
            if filepath in current_tree_files and current_tree_files.get(filepath).sha1 != entry.getSha1Str():
                # This file (that is in the index) is already in the current tree, but its hash in the tree is different
                # Thus, it has been modified and that modification has been staged
                staged_changes.append(f"modified:   {filepath}")

    # TODO: above block should only handle non-conflict entries, and here we should handle conflict entries
    # important: conflicts should come from the index, not from the working tree


    if current_commit is not None:
        current_tree = current_commit.getTree()
        current_tree_files = current_tree.getFiles()

        for filepath in current_tree_files.keys():
            if not os.path.exists(filepath) and not index.containsEntryWithFilepath(filepath):
                # This file exists in the current commit, but not in the index
                # This means it was deleted and removed from the index, so the deletion is staged
                staged_changes.append(f"deleted:    {filepath}")

    if len(staged_changes) > 0:
        print('Changes to be committed:')
        print('  (use "git restore --staged <file>..." to unstage)')
        for change in sorted(staged_changes):
            print(f"{utils.bcolors.OKGREEN}        {change}{utils.bcolors.ENDC}")
        print("")

    if len(unstaged_changes) > 0:
        print('Changes not staged for commit:')
        print('  (use "git add <file>..." to update what will be committed)')
        print('  (use "git restore <file>..." to discard changes in working directory)')
        for change in sorted(unstaged_changes):
            print(f"{utils.bcolors.FAIL}        {change}{utils.bcolors.ENDC}")
        print("")

    if len(untracked_files) > 0:
        print('Untracked files:')
        print('  (use "git add <file>...\" to include in what will be committed)')
        for file in sorted(untracked_files):
            print(f"{utils.bcolors.FAIL}        {file}{utils.bcolors.ENDC}")
        print("")

    if len(untracked_files) == 0 and len(unstaged_changes) == 0 and len(staged_changes) == 0:
        if current_commit is None:
            print('nothing to commit (create/copy files and use "git add" to track)')
        else:
            print('nothing to commit, working tree clean')
    elif len(untracked_files) > 0 and len(unstaged_changes) == 0 and len(staged_changes) == 0:
        print('nothing added to commit but untracked files present (use "git add" to track)')
            

def init(args, prnt=True):    
    repo_name = args.repo_name
    if not os.path.exists(repo_name):
        os.mkdir(repo_name)

    git_dir = os.path.join(repo_name, ".git")
    if os.path.exists(git_dir):
        abort(f"repo already exists at: {git_dir}")
    os.mkdir(git_dir)

    objects_dir = os.path.join(git_dir, "objects")
    refs_dir = os.path.join(git_dir, "refs")
    heads_dir = os.path.join(refs_dir, "heads")
    os.mkdir(objects_dir)
    os.mkdir(refs_dir)
    os.mkdir(heads_dir)

    HEAD_file = GitPath.Path(GitPath.HEAD, prefix=repo_name)
    with open(HEAD_file, "w") as f:
        f.write("ref: refs/heads/main")

    if prnt:
        print(f"Initialized empty Git repository in {os.path.abspath(git_dir)}/")
