import utils
import os
from log import Log
from tree import Tree

class Commit:
    def __init__(self, sha1, tree_hash, author, committer, message, parent=None):
        self.sha1 = sha1
        self.tree_hash = tree_hash
        self.author = author
        self.committer = committer
        self.message = message
        self.parent = parent

    def printLog(self):
        print(f"{utils.bcolors.WARNING}commit {self.sha1}{utils.bcolors.ENDC}", end="")
        modifiers = []
        if Commit.CurrentCommitHash() == self.sha1:
            # TODO: is this the right condition?
            modifiers.append(f"{utils.bcolors.OKCYAN}HEAD -> {utils.bcolors.OKGREEN}{utils.current_branch()}{utils.bcolors.ENDC}")
        
        for branch in utils.all_branches():
            if branch == utils.current_branch():
                continue

            head_filepath = os.path.join(".git", "refs", "heads", branch)
            with open(head_filepath, "r") as f:
                branch_commit = f.read().strip()
                if branch_commit == self.sha1:
                    modifiers.append(f"{utils.bcolors.OKGREEN}{branch}{utils.bcolors.OKCYAN}")

        # TODO: add tags to modifiers once tags are implemented

        if len(modifiers) > 0:
            modifier_connector = f"{utils.bcolors.WARNING}, {utils.bcolors.ENDC}"
            modifiers_str = modifier_connector.join(modifiers)
            print(f" {utils.bcolors.WARNING}({modifiers_str}{utils.bcolors.WARNING}){utils.bcolors.ENDC}", end="")
        print("")
        print(f"    author {self.author}")
        print(f"    committer {self.committer}")
        print("")
        print(f"    {self.message}\n")
        if self.parent is not None:
            Commit.FromHash(self.parent).printLog()

    def getTree(self):
        return Tree.FromHash(self.tree_hash)

    # Returns the current commit object for the current branch, or None if there are no commits
    def CurrentCommitHash():
        current_branch = utils.current_branch()
        if current_branch is None: 
            return None
        
        head_file = os.path.join(".git", "refs", "heads", current_branch)
        if not os.path.exists(head_file): 
            return None
        
        commit_hash = None
        with open(head_file, "r") as f:
            commit_hash = f.read().strip()

        return commit_hash
    
    def FromHash(commit_hash):
        if commit_hash is None:
            return None

        file_contents = utils.read_object_file(commit_hash)
        content = file_contents.split(b"\x00")[1]
        lines = [part for part in content.split(b"\n") if part != b'']
        tree = None
        parent = None
        author = None
        committer = None
        message = None

        for i in range(len(lines)):
            line = lines[i]

            if i == len(lines) - 1:
                message = line.decode('utf-8')
            else:
                parts = line.decode('utf-8').split(" ")
                key = parts[0]
                val = " ".join(parts[1:])
                if key == "tree":
                    tree = val
                elif key == "parent":
                    parent = val
                elif key == "author":
                    author = val
                elif key == "committer":
                    committer = val
        
        return Commit(commit_hash, tree, author, committer, message, parent)
            
        