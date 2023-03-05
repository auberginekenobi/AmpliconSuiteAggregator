###
# Author: Edwin Huang
# This script takes in completed AmpliconArchitect and
# AmpliconClassifier results and aggregates the results.
###
import argparse
import sys
import tarfile
import os
import re
import pandas as pd
import tarfile
import shutil
import json
import subprocess
import ast
import zipfile



class Aggregator():
    def __init__(self, filelist, root, output_name):
        self.filelist_fp = filelist
        self.root = root
        self.output_name = output_name
        self.get_zip_paths()
        self.unzip()
        self.aggregate_tables()
        self.json_modifications()
        # self.move_files()
        # self.cleanup()



    def get_zip_paths(self):
        """
        Gets the individual file paths from the list of zip filepaths

        calls from self
        returns --> a list of filepaths to zip files
        """
        files = []
        with open(self.filelist_fp, 'r') as filelist:
            for line in filelist:
                parsed = line.strip()
                files.append(parsed)
        filelist.close()
        self.zip_paths = files
        return files

    def unzip_file(self, fp, dest_root):
        """
        unzips file based on zip type
        """
        try:
            if ".tar.gz" in fp:
                zip_name = os.path.basename(fp).replace(".tar.gz", "")
                destination = f'./{dest_root}/{zip_name}'
                with tarfile.open(fp, 'r') as output_zip:
                    output_zip.extractall(destination)
                output_zip.close()
            elif ".zip" in fp:
                    zip_name = os.path.basename(fp).replace(".zip", "")
                    destination = f'./{dest_root}/{zip_name}'
                    with zipfile.ZipFile(fp, 'r') as zip_ref:
                        zip_ref.extractall(destination)
                    zip_ref.close()
        except:
            print(f'No need to extract: ./{fp}/{dest_root}')

    def unzip(self):
        """
        Unzips the zip files, and get directories for files within

        returns -- a list of samples, root directory of where the files are located.
        """

        # os.mkdir('all_AA_results')

        for zip_fp in self.zip_paths:
            fp = os.path.join(self.root, zip_fp)
            try:
                dest_root = 'extracted_from_zips'
                self.unzip_file(fp, dest_root)

            except Exception as e:
                print("The zip: " + fp + " ran into an error when unzipping.")
                print(e)
                ## Check if extracted contents is a directory,
                ## and if there is only one directory. Make that the new sample_name
                ## and move it upwards.
                # if len(os.listdir(destination)) == 1:
                #     for file in os.listdir(destination):
                #         if os.path.isdir(f"/opt/genepatt/AA_outputs/{zip_name}/{file}"):
                #             os.system(f"mv -v /opt/genepatt/AA_outputs/{zip_name}/{file} /opt/genepatt/AA_outputs/{file}")
                #             os.system(f"rm -r /opt/genepatt/AA_outputs/{zip_name}/")

        ## find all nested zips and extract them. 
        for root, dirs, files in os.walk(dest_root):
            for file in files:
                fp = os.path.join(root, file)
                self.unzip_file(fp, dest_root)

        ## moving required AA files to correct destination
        output_dir = "./output/AA_outputs/"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        ## find samples and move files
        samples = []
        for root, dirs, files in os.walk(dest_root, topdown = True):
            for dir in dirs: 
                fp = os.path.join(root, dir)
                try:
                    sample_name = re.findall(f'^{dest_root}\/.*\/(.*)_AA_results$', fp)[0]
                    samples.append(sample_name)
                    
                    shutil.move(os.path.dirname(fp), output_dir)
                except:
                    continue
        return samples, dest_root
        
    def aggregate_tables(self):
        """
        From the unzipped paths, start aggregating results
        This function will put together the separate AA runs into one run. 


        """

        output_head = ["Sample name", "AA amplicon number", "Feature ID", "Classification", "Location", "Oncogenes",
                           "Complexity score",
                           "Captured interval length", "Feature median copy number", "Feature maximum copy number",
                           "Reference version", "Feature BED file", "CNV BED file", "AA PNG file", "AA PDF file",
                           "Run metadata JSON"]
        aggregate = pd.DataFrame(columns = output_head)
        runs = {}
        sample_num = 1
        # aggregate results
        for root, dirs, files in os.walk("./output/AA_outputs", topdown = False):
            for name in files:
                if "_result_table.tsv" in name:
                    result_table_fp = os.path.join(root, name)
                    try:
                        df = pd.read_csv(result_table_fp, delimiter = '\t')
                        aggregate = pd.concat([aggregate, df], ignore_index = True)
                        runs[f'sample_{sample_num}'] = json.loads(df.to_json(orient = 'records'))
                        sample_num += 1
                    except:
                        continue

        ## output the table
        aggregate.to_csv('./output/aggregated_results.csv')
        aggregate.to_html('./output/aggregated_results.html')
        with open('./output/run.json', 'w') as run_file:
            json.dump({'runs': runs}, run_file)
        run_file.close()


    def aggregate_json(self, json_files):
        """
        Aggregates json files from separate samples

        """
        out_dict = {'run' : {}}
        sample_ct = 1
        for fp in json_files:
            sample_dict = json.load(open(fp))
            out_dict['run'][f'sample_{sample_ct}'] = sample_dict
            sample_ct += 1

        with open('run.json', 'w') as out_json:
            json.dump(out_dict, out_json)
        out_json.close()

    def move_files(self):
        """
        Move files to correct location for output
        """
        shutil.move(os.path.join('extracted_from_zips'))


    def tardir(self, path, tar_name):
        """
        compresses the path to a tar_mname
        """
        with tarfile.open(tar_name, "w:gz") as tar_handle:
            for root, dirs, files in os.walk(path):
                for file in files:
                    tar_handle.add(os.path.join(root, file))
        tar_handle.close()

    def cleanup(self):
        """
        Zips the aggregate results, and deletes files for cleanup

        """
        self.tardir('results', f'{self.output_name}.tar.gz')
        shutil.rmtree('results')
        # shutil.rmtree('/opt/genepatt/extracted')


    def json_modifications(self):
        """
        Modify outputs of the final run.json

        Modifications include:
        1. correcting string of list
        2. abslute pathing to relative pathing
        """
        with open('./output/run.json') as json_file:
            dct = json.load(json_file)
        json_file.close()

        for sample in dct['runs'].keys():
            ## String of list to list
            for sample_num in range(len(dct['runs'][sample])):
                try:
                    sample_name = dct['runs'][sample][sample_num]['Sample name']

                    locations = dct['runs'][sample][sample_num]['Location']
                    if "|" in locations:
                        dct['runs'][sample][sample_num]['Location'] = locations.split("|")
                    else:
                        dct['runs'][sample][sample_num]['Location'] = locations.strip('][').split(',')

                    ## feature bed location relative path conversion
                    feature_bed_loc = dct['runs'][sample][sample_num]['Feature BED file']
                    # print(feature_bed_loc)
                    basename = os.path.basename(feature_bed_loc)
                    dct['runs'][sample][sample_num]['Feature BED file'] = f"AA_outputs/{sample_name}/{sample_name}_classification/{sample_name}_classification_bed_files/{basename}"

                    ## aa png file
                    aa_png_location = dct['runs'][sample][sample_num]['AA PNG file']
                    basename = os.path.basename(aa_png_location)
                    dct['runs'][sample][sample_num]['AA PNG file'] = f"AA_outputs/{sample_name}/{sample_name}_AA_results/{basename}"

                    ## aa pdf file
                    aa_pdf_location = dct['runs'][sample][sample_num]['AA PDF file']
                    basename = os.path.basename(aa_pdf_location)
                    dct['runs'][sample][sample_num]['AA PDF file'] = f"AA_outputs/{sample_name}/{sample_name}_AA_results/{basename}"

                    ## aa summary file
                    aa_summary_location = dct['runs'][sample][sample_num]['AA summary file']
                    basename = os.path.basename(aa_summary_location)
                    dct['runs'][sample][sample_num]['AA summary file'] = f"AA_outputs/{sample_name}/{sample_name}_AA_results/{basename}"


                    ## cnv bed file
                    cnv_bed_location = dct['runs'][sample][sample_num]['CNV BED file']
                    basename = os.path.basename(cnv_bed_location)
                    dct['runs'][sample][sample_num]['CNV BED file'] = f"AA_outputs/{sample_name}/{sample_name}_classification/files/{basename}"

                    ## run metadata json
                    metadata_json_location = dct['runs'][sample][sample_num]['"Run metadata JSON"']
                    basename = os.path.basename(metadata_json_location)
                    dct['runs'][sample][sample_num]['AA PDF file'] = f"AA_outputs/{sample_name}/{basename}"



                except Exception as e:
                    print(e)

                try:
                    oncogenes = dct['runs'][sample][sample_num]['Oncogenes']
                    if "|" in oncogenes:
                        dct['runs'][sample][sample_num]['Oncogenes'] = oncogenes.split("|")
                    else:
                        dct['runs'][sample][sample_num]['Oncogenes'] = oncogenes.strip('][').split(',')

                except:
                    print(f"Oncogene for sample{sample_num} is None")




        with open('./output/run.json', 'w') as json_file:
            json.dump(dct, json_file)
        json_file.close()

    def absolute_to_relative_fp(fp, sample_name):
        """
        Converts an absolute file path to a relative file path
        """

        filename = os.path.basename(fp)
        return f"AA_outputs/{sample_name}/{sample_name}_classification/"

def validate():
    """
    Validates that all of the file locations exist. 

    
    """
    ## check that everything is in the right place
    if os.path.exists('./output'):
        print('output folder exists')
    else:
        raise Exception("OUTPUT FOLDER NOT CREATED...")
    
    with open('./output/run.json') as json_file:
        dct = json.load(json_file)
    json_file.close()

    ## go through fields to see if each datatype is consistent
    ## and that paths exist
    