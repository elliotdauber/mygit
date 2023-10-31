import utils
import os
from log import Log
from tree import Tree
import re
from datetime import datetime

class Commit:
    def __init__(self, sha1, tree_hash, author, committer, message, parents=[]):
        self.sha1 = sha1
        self.tree_hash = tree_hash
        self.author = author
        self.committer = committer
        self.message = message
        self.parents = parents

    def __eq__(self, other):
        if isinstance(other, Commit):
            return self.sha1 == other.sha1
        return False
    
    def __hash__(self):
        return hash(self.sha1)
    
    def getParentHash(self, parent_idx=0):
        # TODO: possible to have no parents? (first commit)
        return self.parents[parent_idx if len(self.parents) > 1 else 0]
    
    def getCommitHash(self):
        return self.sha1

    # returns all reachable Commits starting from the current Commit
    def reachableCommits(self):
        reachable = [self]
        for parent in self.parents:
            reachable.extend(Commit.FromHash(parent).reachableCommits())

        return sorted(list(set(reachable)), key=lambda commit : commit.commitDateTime(), reverse=True)
                      
    def commitDateTime(self):
        match = re.search(r'\b\d+\b', self.committer)
        if match:
            timestamp = int(match.group())
            commit_datetime = datetime.utcfromtimestamp(timestamp)
            return commit_datetime
        return datetime.MINYEAR

    # TODO: this is kinda awkward because we access the commit data from each reachable commit
    # instead of letting the commits print themselves
    def printLog(self, args):
        commits_to_print = self.reachableCommits()
        if args.reverse:
            commits_to_print.reverse()

        commits_left = args.n if args.n is not None else len(commits_to_print)
        grep_str = args.grep
            
        for commit in commits_to_print:
            if commits_left == 0:
                break
            
            # TODO: use full grep regex and color matches
            if grep_str is not None and commit.message.find(grep_str) == -1:
                continue

            modifiers = []
            if Commit.CurrentCommitHash() == commit.sha1:
                # TODO: is this the right condition?
                modifiers.append(f"{utils.bcolors.OKCYAN}HEAD -> {utils.bcolors.OKGREEN}{utils.current_branch()}{utils.bcolors.ENDC}")
            
            for branch in utils.all_branches():
                if branch == utils.current_branch():
                    continue

                head_filepath = os.path.join(".git", "refs", "heads", branch)
                with open(head_filepath, "r") as f:
                    branch_commit = f.read().strip()
                    if branch_commit == commit.sha1:
                        modifiers.append(f"{utils.bcolors.OKGREEN}{branch}{utils.bcolors.OKCYAN}")

            modifiers_str = ""
            if len(modifiers) > 0:
                modifier_connector = f"{utils.bcolors.WARNING}, {utils.bcolors.ENDC}"
                modifiers_str = f" {utils.bcolors.WARNING}({modifier_connector.join(modifiers)}{utils.bcolors.WARNING}){utils.bcolors.ENDC}"
            # TODO: add tags to modifiers once tags are implemented
            
            if args.oneline:
                print(f"{utils.bcolors.WARNING}{utils.shortened_hash(commit.sha1)}{utils.bcolors.ENDC}{modifiers_str} {commit.message}")
            else:
                print(f"{utils.bcolors.WARNING}commit {commit.sha1}{utils.bcolors.ENDC}{modifiers_str}")
                print(f"    author {commit.author}")
                print(f"    committer {commit.committer}")
                print("")
                print(f"    {commit.message}\n")

            commits_left -= 1

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
        parents = []
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
                    parents.append(val)
                elif key == "author":
                    author = val
                elif key == "committer":
                    committer = val
        
        return Commit(commit_hash, tree, author, committer, message, parents)
            
        