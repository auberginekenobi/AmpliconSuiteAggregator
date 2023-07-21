#!/usr/bin/env python3

import argparse
import socket

from AmpliconSuiteAggregatorFunctions import *
from ASA_POST import * 

__version__ = "2.1"


def get_zip_paths(filelist_fp):
    """
    Gets the individual file paths from the list of zip filepaths

    calls from self
    returns --> a list of filepaths to zip files
    """
    files = []
    with open(filelist_fp) as filelist:
        for line in filelist:
            parsed = line.strip()
            if parsed:
                files.append(parsed)

    return files


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-flist", "--filelist", type=str, help="Text file with files to use (one per line)")
    group.add_argument("--files", nargs='+', type=str, help="List of files or directories to use")
    parser.add_argument("-o", "--output_name", type=str, help="Output Prefix and/or project name for site upload", default="output")
    parser.add_argument("-u", "--username", type=str, help = "Email address for Amplicon Repository. Setting this will "
                        "trigger an attempt to upload the aggregated file to AmpliconRepository.org", required=False)
    # parser.add_argument('-t', '--testing', action = 'store_true', required = False)  # JL: This seems to be unused
    parser.add_argument("--upload_only", type=str, help="If 'Yes', then skip aggregation and classification and upload "
                        "the file as is. Note: the file must already be aggregated to successfully upload.",
                        choices=['Yes', ])
    parser.add_argument("-c", "--run_classifier",type=str, help="If 'Yes', then run Amplicon Classifier on AA results. \
                        If Amplicon Classifier results are already included in inputs, they will be removed and re-classified.",
                        choices=['Yes', ])
    parser.add_argument("-s", "--server", type=str, help="Which server to send results to. Accepts 'dev' or 'prod'. ",
                        choices=['dev', 'prod'])
    parser.add_argument("--ref", type=str, help="Reference genome name used for alignment, one of hg19, GRCh37, GRCh38, GRCh38_viral, or mm10",
                        choices=["hg19", "GRCh37", "GRCh38", "GRCh38_viral", "mm10"])
    parser.add_argument("--python3_path", type=str, help="Specify a custom path to a python3 executable, assumes system path by default",
                        default='python3')
    parser.add_argument("-v", "--version", action='version', version=__version__)
    args = parser.parse_args()

    if args.run_classifier == "Yes" and not args.ref:
        sys.stderr.write("--ref must be specified if -c/--run_classifier is set!\n")
        sys.exit(1)

    if args.upload_only and not args.username:
        sys.stderr.write("-u/--username must be specified if --upload_only is set!\n")
        sys.exit(1)

    if args.username and not args.server:
        sys.stderr.write("-s/--server must be specified if -u/--username is set!\n")
        sys.exit(1)

    if args.filelist:
        filelist = get_zip_paths(args.filelist)

    else:
        filelist = args.files

    root = '.'
    print("AmpliconSuiteAggregator version " + __version__)
    if not args.upload_only:
        # Do the aggregation
        aggregate = Aggregator(filelist, root, args.output_name, args.run_classifier, args.ref, args.python3_path,
                               args.name_map)
        output_fp = args.output_name + ".tar.gz"
        output_list = [output_fp, ]
    else:
        # only uploading a file to the server
        output_list = filelist
        # first check that it is a valid aggregation
        for f in output_list:
            if not f.endswith(".tar.gz"):
                sys.stderr.write(f + " does not appear to be a .tar.gz file!")
                sys.exit(1)

            try:
                tar = tarfile.open(f)
                tar.getmember('./results/run.json')
            except Exception as e:
                sys.stderr.write(str(e) + "\n")
                sys.stderr.write(f + " does not appear to be properly aggregated. Please run the Aggregator before uploading!\n")
                sys.exit(1)

    if args.username:
        current_path = os.getcwd()
        for output_fp in output_list:
            try:
                ## get the job number of the commandline, something like (from genepattern job number)
                ## get pwd and get the job number from there.
                job_number = int(current_path.split('/')[-1])
                desc = f'Results transferred from GenePattern, job id: {job_number}'
            except ValueError:
                job_number = None
                hostname = socket.gethostname()
                desc = f'Results transferred from CLI, hostname: {hostname}'

            ## testrun:
            # python3 /files/src/AmpliconSuiteAggregator.py -flist /inputs/input_list.txt -u $USER
            # python3 AmpliconSuiteAggregator.py -flist /inputs/input_list.txt --run_classifier Yes

            # uploading multiple samples? append the file basename to it
            if len(output_list) > 1:
                projname = os.path.basename(args.output_name) + "_" + os.path.basename(output_fp[:-7])
            else:
                projname = os.path.basename(args.output_name)

            user = args.username
            data = {'project_name': os.path.basename(projname),
                    'description': desc,
                    'private': True,
                    'project_members': [args.username],}

            print(f'Creating project for user: {user}')
            post_package(output_fp, data, args.server)
