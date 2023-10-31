import argparse

class GitArgParser:
    instance = None

    def __init__(self):
        self.parser = argparse.ArgumentParser(description='mygit argparser')
        subparsers = self.parser.add_subparsers(dest='command')

        init_subparser = subparsers.add_parser('init')
        init_subparser.add_argument('repo_name')
        
        add_subparser = subparsers.add_parser('add')
        add_subparser.add_argument('file')

        commit_subparser = subparsers.add_parser('commit')
        commit_subparser.add_argument('-m', nargs='+')

        log_subparser = subparsers.add_parser('log')
        log_subparser.add_argument('rev', nargs='?', default=None)
        log_subparser.add_argument('-n', type=int)
        log_subparser.add_argument('--grep')
        log_subparser.add_argument('--oneline', action='store_true')
        log_subparser.add_argument('--reverse', action='store_true')

        merge_subparser = subparsers.add_parser('merge')
        merge_subparser.add_argument('rev')

        cherry_pick_subparser = subparsers.add_parser('cherry-pick')
        cherry_pick_subparser.add_argument('commit_rev')
        cherry_pick_subparser.add_argument('-m', type=int)

        rebase_subparser = subparsers.add_parser('rebase')
        rebase_subparser.add_argument('rev')

        reflog_subparser = subparsers.add_parser('reflog')

        merge_base_subparser = subparsers.add_parser('merge-base')
        merge_base_subparser.add_argument('rev1')
        merge_base_subparser.add_argument('rev2')

        diff_subparser = subparsers.add_parser('diff')
        diff_subparser.add_argument('rev1', nargs='?', default=None)
        diff_subparser.add_argument('rev2', nargs='?', default=None)

        branch_subparser = subparsers.add_parser('branch')
        branch_subparser.add_argument('-d', action="store_true")
        branch_subparser.add_argument('branch_name', nargs='?', default=None)

        tag_subparser = subparsers.add_parser('tag')
        tag_subparser.add_argument('-d', action="store_true")
        tag_subparser.add_argument('tag_name', nargs='?', default=None)

        restore_subparser = subparsers.add_parser('restore')
        restore_subparser.add_argument('--staged', action='store_true')
        restore_subparser.add_argument('file')

        rm_subparser = subparsers.add_parser("rm")
        rm_subparser.add_argument("file")

        ls_files_subparser = subparsers.add_parser('ls-files')
        ls_files_subparser.add_argument('-s', action='store_true')
        ls_files_subparser.add_argument('--abbrev', action='store_true')

        rev_parse_subparser = subparsers.add_parser('rev-parse')
        rev_parse_subparser.add_argument('rev')

        stash_subparser = subparsers.add_parser('stash')
        stash_subparser.add_argument('command', nargs='?', default=None)

        checkout_subparser = subparsers.add_parser('checkout')
        checkout_subparser.add_argument('-b', action='store_true')
        checkout_subparser.add_argument('branch_name')

        hash_object_subparser = subparsers.add_parser('hash-object')
        hash_object_subparser.add_argument('--stdin', action='store_true')
        hash_object_subparser.add_argument('-w', action='store_true')
        hash_object_subparser.add_argument('filename', nargs='?', default=None)

        cat_file_subparser = subparsers.add_parser('cat-file')
        cat_file_subparser.add_argument('-p', action='store_true')
        cat_file_subparser.add_argument('-t', action='store_true')
        cat_file_subparser.add_argument('object_hash')

        update_index_subparser = subparsers.add_parser('update-index')
        update_index_subparser.add_argument('--add', action='store_true')
        update_index_subparser.add_argument('--remove', action='store_true')
        update_index_subparser.add_argument('--cacheinfo', action='store_true')
        update_index_subparser.add_argument('arg1')
        update_index_subparser.add_argument('arg2', nargs='?', default=None)
        update_index_subparser.add_argument('arg3', nargs='?', default=None)

        update_ref_subparser = subparsers.add_parser('update-ref')
        update_ref_subparser.add_argument('ref_file')
        update_ref_subparser.add_argument('commit_hash')

        status_subparser = subparsers.add_parser('status')
        read_index_subparser = subparsers.add_parser('read-index')
        write_tree_subparser = subparsers.add_parser('write-tree')

    @staticmethod
    def Instance():
        if GitArgParser.instance is None:
            GitArgParser.instance = GitArgParser()
        return GitArgParser.instance
    
    @staticmethod
    def Parse(argstring=None):
        if argstring is None:
            return GitArgParser.Instance().parser.parse_args()

        return GitArgParser.Instance().parser.parse_args(argstring.split())
    
    def Execute(argstring=None):
        args = GitArgParser.Parse(argstring)

        import commands
        if args.command == "init":
            return commands.init(args)
        elif args.command == "add":
            return commands.add(args)
        elif args.command == 'status':
            return commands.status()
        elif args.command == 'log':
            return commands.log(args)
        elif args.command == 'commit':
            return commands.commit(args)
        elif args.command == 'stash':
            return commands.stash(args)
        elif args.command == 'branch':
            return commands.branch(args)
        elif args.command == 'tag':
            return commands.tag(args)
        elif args.command == 'checkout':
            return commands.checkout(args)
        elif args.command == 'merge':
            return commands.merge(args)
        elif args.command == 'cherry-pick':
            return commands.cherry_pick(args)
        elif args.command == 'rebase':
            return commands.rebase(args)
        elif args.command == 'merge-base':
            return commands.merge_base(args)
        elif args.command == 'restore':
            return commands.restore(args)
        elif args.command == 'ls-files':
            return commands.ls_files(args)
        elif args.command == 'reflog':
            return commands.reflog(args)
        elif args.command == 'rev-parse':
            return commands.rev_parse(args)
        elif args.command == 'diff':
            return commands.diff(args)
        elif args.command == "hash-object":
            return commands.hash_object(args)
        elif args.command == "cat-file":
            return commands.cat_file(args)
        elif args.command == 'update-index':
            return commands.update_index(args)
        elif args.command == 'write-tree':
            return commands.write_tree()
        elif args.command == 'read-index':
            return commands.read_index()
        elif args.command == 'update-ref':
            return commands.update_ref(args)
        else:
            print(f"unknown command: {args.command}")
            exit(1)

