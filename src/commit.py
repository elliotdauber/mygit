import utils
import os
from log import Log
from tree import Tree
import re
from datetime import datetime, timedelta

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
        if self.numParents() == 0:
            return None
        return self.parents[parent_idx if len(self.parents) > 1 else 0]
    
    def numParents(self):
        return len(self.parents)
    
    def getCommitHash(self):
        return self.sha1

    # returns all reachable Commits starting from the current Commit
    def reachableCommits(self):
        reachable = [self]
        for parent in self.parents:
            reachable.extend(Commit.FromHash(parent).reachableCommits())

        return sorted(list(set(reachable)), key=lambda commit : commit.commitDateTime(), reverse=True)

    def commitAuthor(self):
        # TODO: could be more complicated edge cases
        return self.author[:self.author.find('>') + 1]

    # String representation of datetime, including utc_offset
    def commitDateTimeStr(self):
        timestamp, utc_offset = self.committer[self.committer.find('>') + 2:].split(" ")
        return f"{datetime.fromtimestamp(int(timestamp)).strftime('%a %b %d %H:%M:%S %Y')} {utc_offset}"

    # Does not include utc offset
    def commitDateTime(self):
        # TODO: could be more complicated edge cases
        timestamp, utc_offset = self.committer[self.committer.find('>') + 2:].split(" ")
        hours, minutes = int(utc_offset[0] + utc_offset[1:3]), int(utc_offset[3:5])
        offset = timedelta(hours=hours, minutes=minutes)
        return datetime.fromtimestamp(int(timestamp)) - offset

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

            modifier_str = utils.branch_summary_for_commit(commit.getCommitHash())
            if len(modifier_str) > 0:
                modifier_str = " " + modifier_str
            
            if args.oneline:
                print(f"{utils.bcolors.WARNING}{utils.shortened_hash(commit.sha1)}{utils.bcolors.ENDC}{modifier_str} {commit.message}")
            else:
                print(f"{utils.bcolors.WARNING}commit {commit.sha1}{utils.bcolors.ENDC}{modifier_str}")
                if commit.numParents() > 1:
                    print("Merge: ", end="")
                    for i in range(commit.numParents()):
                        print(utils.shortened_hash(commit.getParentHash(i)), end=" ")
                    print("")
                # print(f"    author {commit.author}")
                # print(f"    committer {commit.committer}")
                print(f"Author: {commit.commitAuthor()}")
                print(f"Date:   {commit.commitDateTimeStr()}")
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
            
        