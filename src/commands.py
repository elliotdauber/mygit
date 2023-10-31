import sys
import os
import utils
from datetime import datetime
from index import Index, IndexEntry
from log import Log
from commit import Commit
from tree import Tree, Blob
from argparser import GitArgParser
from diff import CommitDiff, DiffTraceAction
from gitpath import GitPath


MAIN_COMMAND = "mygit"

def abort(err):
    print(err)
    exit(1)

def rev_parse(args, prnt=True):
    rev = args.rev

    symbolic_rev_files = ["HEAD", "ORIG_HEAD"]
    result = None
    ambigious = False

    if utils.is_valid_hash(rev):
        result = rev
    elif rev in symbolic_rev_files:
        file = os.path.join(".git", rev)
        if os.path.exists(file):
            with open(file, "r") as f:
                content = f.read().strip()
                if content.startswith("ref: "):
                    ref = content.split("ref: ")[1]
                    result = utils.commit_hash_from_ref(ref)
                elif utils.is_valid_hash(content):
                    result = content   
    else:        
        (result, ambigious) = utils.commit_hash_from_ref(rev)
    
    if prnt:
        if result is None:
            print(rev)
            print(f"fatal: ambiguous argument '{rev}': unknown revision or path not in the working tree.")
            # print("Use '--' to separate paths from revisions, like this:")
            # print("'git <command> [<revision>...] -- [<file>...]'")
        else:
            if ambigious:
                print(f"warning: refname '{rev}' is ambiguous.")
            print(result)

    return result

def stash(args):
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
        rev1_hash = rev_parse(GitArgParser.Parse(f"rev-parse {rev1}"), prnt=False)
        rev2_hash = rev_parse(GitArgParser.Parse(f"rev-parse {rev2}"), prnt=False)
        tree1, tree2 = Commit.FromHash(rev1_hash).getTree(), Commit.FromHash(rev2_hash).getTree()
        commit_diff = CommitDiff(tree1, tree2)

    if commit_diff is not None and prnt:
        commit_diff.print()

    return commit_diff


# returns the hash of the merge base given two revisions
def merge_base(args, prnt=True):
    rev1 = args.rev1
    rev2 = args.rev2

    rev1_hash = rev_parse(GitArgParser.Parse(f"rev-parse {rev1}"), prnt=False)
    rev2_hash = rev_parse(GitArgParser.Parse(f"rev-parse {rev2}"), prnt=False)

    rev1_reachable_commits = Commit.FromHash(rev1_hash).reachableCommits()
    rev2_reachable_commits = Commit.FromHash(rev2_hash).reachableCommits()

    common_ancestors = set(rev1_reachable_commits).intersection(set(rev2_reachable_commits))
    if len(common_ancestors) > 0:
        most_recent_common_ancestor = sorted(list(common_ancestors), key=lambda commit: commit.commitDateTime(), reverse=True)[0].sha1
        if prnt:
            print(most_recent_common_ancestor)
        return most_recent_common_ancestor
    return None
    
class MergeConflict:
    def __init__(self, filepath, base_file_hash, source_file_hash, target_file_hash, start_lineno, source_label, target_label):
        self.filepath = filepath # TODO: doesn't work for renames
        self.base_file_hash = base_file_hash
        self.source_file_hash = source_file_hash
        self.target_file_hash = target_file_hash
        self.start_lineno = start_lineno
        self.source_label = source_label
        self.target_label = target_label
        self.source_lines = []
        self.target_lines = []

    def addTargetLine(self, line):
        self.target_lines.append(line)

    def addSourceLine(self, line):
        self.source_lines.append(line)

    def getStartLineno(self):
        return self.start_lineno

    def getAllLines(self):
        if len(self.target_lines) + len(self.source_lines) == 0:
            return []

        all_lines = []
        all_lines.append(f"<<<<<<< {self.target_label}")
        for line in self.target_lines:
            all_lines.append(line)
        all_lines.append("=======")
        for line in self.source_lines:
            all_lines.append(line)
        all_lines.append(f">>>>>>> {self.source_label}")
        return all_lines
    
    def getBaseFileHash(self):
        return self.base_file_hash
    
    def getSourceFileHash(self):
        return self.source_file_hash
    
    def getTargetFileHash(self):
        return self.target_file_hash
    
def rebase(args):
    merge_source_rev = args.rev
    target_branch_name = utils.current_branch()

    merge_source_hash = rev_parse(GitArgParser.Parse(f"rev-parse {merge_source_rev}"), prnt=False)
    merge_target_hash = rev_parse(GitArgParser.Parse(f"rev-parse {target_branch_name}"), prnt=False)

    # If the commit hashes of the source and destination are the same, nothing to do
    if merge_source_hash == merge_target_hash:
        print("Already up to date.")
        return

    # find the merge base
    merge_base_hash = merge_base(GitArgParser.Parse(f"merge-base {args.branch_name} {target_branch_name}"), prnt=False)

    abort('unimplemented')

def cherry_pick(args):
    commit_rev = args.commit_rev
    commit_hash = rev_parse(GitArgParser.Parse(f"rev-parse {commit_rev}"), prnt=False)
    parents = Commit.FromHash(commit_hash).parents

    if len(parents) > 1 and not args.m:
        print(f"error: commit {commit_hash} is a merge but no -m option was given.")
        abort("fatal: cherry-pick failed")

    abort('unimplemented')

    with open(GitPath.Path(GitPath.CHERRY_PICK_HEAD), "w") as f:
        f.write(commit_hash)

def merge(args):
    merge_source_rev = args.rev
    target_branch_name = utils.current_branch()

    merge_source_hash = rev_parse(GitArgParser.Parse(f"rev-parse {merge_source_rev}"), prnt=False)
    merge_target_hash = rev_parse(GitArgParser.Parse(f"rev-parse {target_branch_name}"), prnt=False)

    # If the commit hashes of the source and destination are the same, nothing to do
    if merge_source_hash == merge_target_hash:
        print("Already up to date.")
        return

    # source_reachable_commits = Commit.FromHash(merge_source_hash).reachableCommits()
    # current_branch_reachable_commits = Commit.FromHash(current_branch_hash).reachableCommits()

    # find the merge base
    merge_base_hash = merge_base(GitArgParser.Parse(f"merge-base {args.branch_name} {target_branch_name}"), prnt=False)

    # TODO: is this the only condition? what if merge_base_hash is in the history of current branch?
    # maybe gets more complicated with 
    if merge_base_hash == merge_target_hash:
        # This is a fast forward, just update current branch's head pointer
        print(f"Updating {utils.shortened_hash(merge_target_hash)}..{utils.shortened_hash(merge_source_hash)}")
        print("Fast-Forward")

        commit_diff = diff(GitArgParser.Parse(f"diff {merge_base_hash} {merge_source_hash}"), prnt=False)
        if commit_diff is not None:
            file_diffs = commit_diff.getFileDiffs()
            changes_to_print = {}
            num_insertions = 0
            num_deletions = 0
            for dff in file_diffs:
                if not dff.filepathChanged():
                    insertions_str = f"{utils.bcolors.OKGREEN}{'+' * dff.numInsertions()}{utils.bcolors.ENDC}"
                    deletions_str = f"{utils.bcolors.FAIL}{'-' * dff.numDeletions()}{utils.bcolors.ENDC}"
                    changes_to_print[dff.base_filepath] = f"{dff.numChanges()} {insertions_str}{deletions_str}"
                    num_insertions += dff.numInsertions()
                    num_deletions += dff.numDeletions()

            # print the changes overview for each file
            rhs_length = sorted(map(lambda fp : len(fp), changes_to_print.keys()))[-1]
            for filepath, change in sorted(changes_to_print.items()):
                print(f" {filepath}{' ' * (rhs_length - len(filepath))} | {change}")

            # print the overall summary
            summary_parts = [f"{len(changes_to_print)} files changed"]
            if num_insertions > 0:
                summary_parts.append(f"{num_insertions} insertions(+)")
            if num_deletions > 0:
                summary_parts.append(f"{num_deletions} deletions(-)")
            print(f" {', '.join(summary_parts)}")

        # update the files (for a fast-forward this is easy)
        utils.update_files_to_commit_hash(merge_source_hash)
        GitArgParser.Execute(f"update-ref {os.path.join('refs', 'heads', target_branch_name)} {merge_source_hash}")

    else:
        # 3-way merge

        # get the diff of the current branch against the merge base
        target_commit_diff = diff(GitArgParser.Parse(f"diff {merge_base_hash} {merge_target_hash}"), prnt=False)
        
        # get the diff of the source commit against the merge base
        source_commit_diff = diff(GitArgParser.Parse(f"diff {merge_base_hash} {merge_source_hash}"), prnt=False)

        # print("CURRENT: ")
        # target_commit_diff.print()
        # print("\n\n\n")

        # print("SRC: ")
        # source_commit_diff.print()
        # print("\n\n\n")

        # combine the file diffs into a list of tuples of the form (target_commit_file_diff, source_commit_file_diff)
        # for each file. Either diff can be None
        # TODO: this does not handle renames
        filepaths_target_commit = set([dff.base_filepath for dff in target_commit_diff.getFileDiffs()])
        filepaths_source_commit = set([dff.base_filepath for dff in source_commit_diff.getFileDiffs()])
        all_filepaths = filepaths_target_commit.union(filepaths_source_commit)
        combined_file_diffs = [
            (target_commit_diff.getFileDiff(fp), source_commit_diff.getFileDiff(fp)) 
            for fp in all_filepaths
        ]

        merge_base_files = Commit.FromHash(merge_base_hash).getTree().getFiles()
        source_files = Commit.FromHash(merge_source_hash).getTree().getFiles()
        target_files = Commit.FromHash(merge_target_hash).getTree().getFiles()

        # TODO: can probably get this info from the index after the merging?
        merge_has_conflicts = False
        # merge each file
        for (target_file_diff, source_file_diff) in combined_file_diffs:
            # TODO: this does not handle renames
            filepath = target_file_diff.base_filepath if target_file_diff else source_file_diff.base_filepath
            print(filepath)
            if target_file_diff is None:
                with open(filepath, "w") as f:
                    f.write(source_files[filepath].content)
                GitArgParser.Execute(f"add {filepath}")
            elif source_file_diff is None:
                with open(filepath, "w") as f:
                    f.write(target_files[filepath].content)
                GitArgParser.Execute(f"add {filepath}")
            else:
                print(f"{filepath}")
                # both commits have changed the file, need to reconcile

                # first, get the content of the merge base version
                if filepath not in merge_base_files:
                    abort(f"something is wrong, merge base does not contain the file {filepath}")

                # get the content of each file being merged
                base_file_content = merge_base_files[filepath].content
                source_file_content = source_files[filepath].content
                target_file_content = target_files[filepath].content

                # get the sha1 of each file being merged
                base_file_hash = hash_object(GitArgParser.Parse(f"hash-object"), prnt=False, content_override=base_file_content)
                source_file_hash = hash_object(GitArgParser.Parse(f"hash-object"), prnt=False, content_override=source_file_content)
                target_file_hash = hash_object(GitArgParser.Parse(f"hash-object"), prnt=False, content_override=target_file_content)

                # get the lines for each file being merged
                base_file_lines = base_file_content.split("\n")
                source_file_lines = source_file_content.split("\n")
                target_file_lines = target_file_content.split("\n")
                
                # go through both file diff traces line by line
                target_trace_counter = 0
                source_trace_counter = 0
                base_lineno = 0
                target_lineno = 0
                source_lineno = 0
                target_trace = target_file_diff.trace
                source_trace = source_file_diff.trace

                conflict = None
                conflicts = []
                while True:
                    target_trace_item = target_trace[target_trace_counter] if target_trace_counter < len(target_trace) else None
                    source_trace_item = source_trace[source_trace_counter] if source_trace_counter < len(source_trace) else None

                    target_line = target_file_lines[target_lineno]
                    source_line = source_file_lines[source_lineno]
                    Log.Debug(f"line: {base_file_lines[base_lineno]}, curr: {target_trace_item}, src: {source_trace_item}")

                    in_conflict = False

                    if target_trace_item == DiffTraceAction.MATCH and source_trace_item == DiffTraceAction.MATCH:
                        base_lineno += 1
                        target_trace_counter += 1
                        source_trace_counter += 1
                    elif target_trace_item == DiffTraceAction.MATCH and source_trace_item == DiffTraceAction.DELETE:
                        # delete the line
                        Log.Debug(f"\tDELETE: {base_file_lines[base_lineno]}")
                        base_file_lines.pop(base_lineno)
                        target_trace_counter += 1
                        source_trace_counter += 1
                    elif target_trace_item == DiffTraceAction.MATCH and source_trace_item == DiffTraceAction.ADD:
                        # add the line from source
                        Log.Debug(f"\tADD: {source_line}")
                        base_file_lines.insert(base_lineno, source_line)
                        base_lineno += 1 # inc by 2 to skip the line that was just added
                        source_trace_counter += 1 # Don't increment target_trace item because we need it for the next line

                        target_lineno -= 1
                    elif target_trace_item == DiffTraceAction.DELETE and source_trace_item == DiffTraceAction.DELETE:
                        Log.Debug(f"\tDELETE: {base_file_lines[base_lineno]}")
                        base_file_lines.pop(base_lineno)
                        target_trace_counter += 1
                        source_trace_counter += 1
                    elif target_trace_item == DiffTraceAction.ADD and source_trace_item == DiffTraceAction.ADD:
                        # TODO: this assumes conflicts are all the same length, need more heuristics
                        if target_file_lines[target_lineno] == source_file_lines[source_lineno]:
                            Log.Debug(f"\tMUTUAL_ADD: {target_line}")
                            base_file_lines.insert(base_lineno, target_line)
                            base_lineno += 1
                        else:
                            Log.Debug(f"\tCONFLICT: {target_line}, {source_line}")
                            # base_file_lines.insert(base_lineno, "CONFLICT: " + target_line + ", " + source_line)
                            if conflict is None:
                                # base_blob_hash = 
                                conflict = MergeConflict(filepath,
                                                         base_file_hash,
                                                         source_file_hash,
                                                         target_file_hash,
                                                         base_lineno - 1, 
                                                         merge_source_rev, 
                                                         "HEAD") # TODO: always head??
                            conflict.addSourceLine(source_line)
                            conflict.addTargetLine(target_line)
                            in_conflict = True
                        target_trace_counter += 1
                        source_trace_counter += 1
                        # base_lineno += 1
                    else:
                        break

                    if not in_conflict and conflict is not None:
                        # We had a MergeConflict, but the conflict area ended
                        conflicts.append(conflict)
                        conflict = None

                    if target_trace_item is not None and target_trace_item != DiffTraceAction.DELETE:
                        target_lineno += 1
                    if source_trace_item is not None and source_trace_item != DiffTraceAction.DELETE:
                        source_lineno += 1
                    

                index = Index.FromFile()
                # insert all conflicts
                for conflict in conflicts:
                    conflict_lines = conflict.getAllLines()
                    conflict_start = conflict.getStartLineno()
                    for i in range(len(conflict_lines)):
                        base_file_lines.insert(conflict_start + i, conflict_lines[i])

                    # TODO: won't work for renames, deletions, etc
                    merge_base_entry = IndexEntry.FromFile(filepath, conflict.getBaseFileHash())
                    merge_base_entry.setStageInt(1)
                    index.addEntry(merge_base_entry, key="hash")
                    
                    source_entry = IndexEntry.FromFile(filepath, conflict.getSourceFileHash())
                    source_entry.setStageInt(3)
                    index.addEntry(source_entry, key="hash")

                    target_entry = index.getEntryWithHash(conflict.getTargetFileHash())
                    target_entry.setStageInt(2)
                    index.addEntry(target_entry, key="hash")

                    index.writeToFile()

                # TODO: make this work for renames, deletions, etc
                with open(filepath, "w") as f:
                    content = "\n".join(base_file_lines)
                    f.write(content)

                print(f"Auto-merging {filepath}")
                if len(conflicts) > 0:
                    merge_has_conflicts = True
                    print(f"CONFLICT (content): Merge conflict in {filepath}")
                else:
                    with open(filepath, "w") as f:
                        f.write("\n".join(base_file_lines))
                    GitArgParser.Parse(f"add {filepath}")

        default_merge_commit_msg = f"Merge branch '{merge_source_rev}'"

        if merge_has_conflicts:
            print("Automatic merge failed; fix conflicts and then commit the result.")

            # write to MERGE_HEAD, MERGE_MSG, ORIG_HEAD
            with open(GitPath.Path(GitPath.MERGE_HEAD), "w") as f:
                f.write(merge_source_hash)

            with open(GitPath.Path(GitPath.ORIG_HEAD), "w") as f:
                f.write(merge_target_hash)

            with open(GitPath.Path(GitPath.MERGE_MSG), "w") as f:
                f.write(default_merge_commit_msg, end="\n\n") #TODO doesn't need to be a branch
                f.write("# Conflicts:")
                for conflict in conflicts:
                    print(f"#	{conflict.filepath}")
        else:
            GitArgParser.Execute(f"commit -m \"{default_merge_commit_msg}\"")
                

def commit(args):
    if args.m is None:
        abort("fatal: must supply a message using -m")

    message = " ".join(args.m)

    current_branch = utils.current_branch()
    if current_branch is None:
        abort("fatal: not on a branch")

    parent_commit = None
    ref_file = GitPath.BranchPath(current_branch)
    if os.path.exists(ref_file):
        with open(ref_file, "r") as f:
            parent_commit = f.read()
    tree_hash = write_tree(prnt=False)

    # TODO: add second parent for merges
    signature = utils.signature() # TODO: is author ever different?
    commit_file_content = f'tree {tree_hash}\n{"parent " + parent_commit if parent_commit else ""}\nauthor {signature}\ncommitter {signature}\n\n{message}\n'
    commit_file_header = f'commit {len(commit_file_content)}\0'
    commit_hash = utils.write_object_file((commit_file_header + commit_file_content).encode('utf-8'))
    print(f"[{current_branch} (root-commit) {utils.shortened_hash(commit_hash)}] {message}")

    # TODO: print the other details
    # this will be something of the form: 3 files changed, 5 insertions(+), 3 deletions(-)
    # this is already done in merge(), so just refactor that

    #update refs/heads/{current_branch} with hash of file
    with open(ref_file, "w") as f:
        f.write(commit_hash)

    # update the reflog
    log_file = GitPath.BranchLogPath(current_branch)
    utils.create_intermediate_dirs(log_file)
    with open(log_file, 'a') as f:
        f.write(f"{parent_commit if parent_commit else '0'*40} {commit_hash} {signature}	commit{' (initial)' if not parent_commit else ''}: {message}\n")
    
    # TODO: update HEAD log file?

def add(args):
    filepath = args.file
    # TODO: is it ok to always include --add?
    GitArgParser.Execute(f"update-index --add {'--remove' if not os.path.exists(filepath) else ''} {filepath}")

def restore(args):
    filepath = args.file
    staged = args.staged

    if staged:
        # TODO: for some reason, after running this command, and then using the real git status, the file comes up as deleted
        GitArgParser.Execute(f"update-index --remove {filepath}")
    else:
        abort("unimplemented, gotta figure out what the behavior is here")

def rm(args):
    filepath = args.file

    GitArgParser.Execute(f"update-index --remove {filepath}")

    # TODO: what if filepath is a folder?
    os.remove(filepath)

def log(args):
    rev = args.rev

    commit_hash = None
    if rev is None:
        commit_hash = Commit.CurrentCommitHash()
        if commit_hash is None:
            print(f"fatal: your current branch '{utils.current_branch()}' does not have any commits yet")
            return
    else:
        commit_hash = rev_parse(GitArgParser.Parse(f"rev-parse {rev}"), prnt=False)
        if commit_hash is None:
            print(f"fatal: ambiguous argument '{rev}': unknown revision or path not in the working tree.")
            return
            # print("Use '--' to separate paths from revisions, like this:")
            # print('git <command> [<revision>...] -- [<file>...]')
    commit = Commit.FromHash(commit_hash)
    commit.printLog(args)

def reflog(args):

    if Commit.CurrentCommitHash() is None:
        abort(f"fatal: your current branch '{utils.current_branch()}' does not have any commits yet")

    # TODO: print reflog
    abort('unimplemented')

def branch(args):
    branch_name = args.branch_name
    delete_branch = args.d

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
            print(f"Deleted branch {branch_name} (was {utils.shortened_hash(branch_hash)}).")

        os.remove(ref_file)
        # TODO: could clean up intermediate folders that have become empty
        return
        

    if branch_name is None:
        for branch in utils.all_branches():
            if branch == utils.current_branch():
                print(f"* {utils.bcolors.OKGREEN}{branch}{utils.bcolors.ENDC}")
            else:
                print(f"  {branch}")
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

    # TODO: what to do if no commits yet?
    GitArgParser.Execute(f"update-ref {os.path.join('refs', 'heads', branch_name)} {Commit.CurrentCommitHash()}")

    log_file = GitPath.BranchLogPath(branch_name)
    utils.create_intermediate_dirs(log_file)
    with open(log_file, 'a') as f:
        f.write(f"{'0'*40} {Commit.CurrentCommitHash()} {utils.signature()}	branch: Created from {utils.current_branch()}\n")

def tag(args):
    tag_name = args.tag_name
    delete_tag = args.d
    Log.Debug(tag_name)
    abort('unimplemented, but basically the same as branch')

def checkout(args):
    create_new_branch = args.b
    branch_name = args.branch_name

    if create_new_branch:
        GitArgParser.Execute(f"branch {branch_name}")

    branch_ref_file = GitPath.BranchPath(branch_name)
    branch_commit = None
    with open(branch_ref_file, "r") as f:
        branch_commit = f.read().strip()

    utils.update_files_to_commit_hash(branch_commit)

    # update the HEAD ref
    HEAD_file = GitPath.Path(GitPath.HEAD)
    with open(HEAD_file, "w") as f:
        f.write(f"ref: refs/heads/{branch_name}")

    print(f"Switched to {'a new ' if create_new_branch else ''}branch '{branch_name}'")

    
def update_ref(args):
    ref_file = os.path.join(".git", args.ref_file)
    commit_hash = args.commit_hash

    # TODO: check that args are valid
    with open(ref_file, "w") as f:
        f.write(commit_hash)

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

def write_tree(prnt=True):
    index = Index.FromFile()
    tree_hash = utils.create_tree(index)
    if prnt:
        print(tree_hash)
    return tree_hash

def cat_file(args):
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

def read_index():
    index = Index.FromFile()
    index.print()

def update_index(args):
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

            hash_object_args = GitArgParser.Parse(f"hash-object -w {filepath}")
            object_hash = hash_object(hash_object_args, prnt=False)

            newEntry = IndexEntry.FromFile(filepath, object_hash)
            index.addEntry(newEntry)

    index.writeToFile()
    # Log.Debug("Index after update: ")
    # index.print()

def ls_files(args):
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
        
    
def status():
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
            

def init(args):    
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

    print(f"Initialized empty Git repository in {os.path.abspath(git_dir)}/")