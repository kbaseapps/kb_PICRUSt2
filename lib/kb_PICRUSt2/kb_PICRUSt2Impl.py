# -*- coding: utf-8 -*-
#BEGIN_HEADER
import time
import logging
import os
import sys
import subprocess
import uuid
import functools
import pandas as pd
import numpy as np
import gzip
import shutil
import json

from installed_clients.KBaseReportClient import KBaseReport
from installed_clients.DataFileUtilClient import DataFileUtil
from installed_clients.FunctionalProfileUtilClient import FunctionalProfileUtil
from installed_clients.GenericsAPIClient import GenericsAPI

from .util.kbase_obj import AmpliconMatrix, AttributeMapping
from .util.outfile import OutfileWrangler
from .util.error import *
from .util.dprint import dprint
from .util.config import var, reset_var
from .util.report import HTMLReportWriter
from .util.params import Params


####################################################################################################
####################################################################################################
def run_check(cmd):
    '''Wrap tool-running method for patching'''

    logging.info(f'Running PICRUSt2 via command `{cmd}`')

    t0 = time.time()
    completed_proc = subprocess.run(cmd, shell=True, executable='/bin/bash', stdout=sys.stdout, stderr=sys.stdout)

    logging.info('Completed in %.1f minutes' % ((time.time()-t0)/60))

    if completed_proc.returncode != 0:
        msg = (
            "PICRUSt2 command `%s` returned with non-zero return code `%d`. "
            "Please check logs for more details" % 
            (cmd, completed_proc.returncode)
        )
        raise NonZeroReturnException(msg)

####################################################################################################
####################################################################################################

def gunzip_to(read, write):
    '''
    Gunzip from `read` to `write`
    '''
    with gzip.open(read, 'rb') as fh_read:
        with open(write, 'wb') as fh_write:
            shutil.copyfileobj(fh_read, fh_write)

####################################################################################################
####################################################################################################
#END_HEADER


class kb_PICRUSt2:
    '''
    Module Name:
    kb_PICRUSt2

    Module Description:
    A KBase module: kb_PICRUSt2
    '''

    ######## WARNING FOR GEVENT USERS ####### noqa
    # Since asynchronous IO can lead to methods - even the same method -
    # interrupting each other, you must be *very* careful when using global
    # state. A method could easily clobber the state set by another while
    # the latter method is running.
    ######################################### noqa
    VERSION = "0.0.1"
    GIT_URL = ""
    GIT_COMMIT_HASH = ""

    #BEGIN_CLASS_HEADER
    #END_CLASS_HEADER

    # config contains contents of config file in a hash or None if it couldn't
    # be found
    def __init__(self, config):
        #BEGIN_CONSTRUCTOR
        logging.basicConfig(format='%(created)s %(levelname)s: %(message)s',
                            level=logging.INFO)

        self.callback_url = os.environ['SDK_CALLBACK_URL']
        self.workspace_url = config['workspace-url']
        self.shared_folder = config['scratch']
       
        
        #END_CONSTRUCTOR
        pass


    def run_picrust2_pipeline(self, ctx, params):
        """
        This example function accepts any number of parameters and returns results in a KBaseReport
        :param params: instance of mapping from String to unspecified object
        :returns: instance of type "ReportResults" -> structure: parameter
           "report_name" of String, parameter "report_ref" of String
        """
        # ctx is the context object
        # return variables are: output
        #BEGIN run_picrust2_pipeline
####################################################################################################
####################################################################################################
####################################################################################################
####################################################################################################
####################################################################################################

        #
        ##
        ### params, app-globals, directories, etc
        ####
        #####

        logging.info('BEGINNING KB_PICRUST2. params: %s' % str(params))

        params = Params(params)

        dprint('params', run=locals())
        
        reset_var() # clear all fields but `debug`

        var.update(
            params=params,
            dfu=DataFileUtil(self.callback_url),
            kbr=KBaseReport(self.callback_url),
            fpu=FunctionalProfileUtil(self.callback_url, service_ver='dev'),
            gapi=GenericsAPI(self.callback_url, service_ver='dev'),
            shared_folder=self.shared_folder,
            run_dir=os.path.join(self.shared_folder, 'run_dir_picrust2_' + str(uuid.uuid4())),
            warnings=[],
            objects_created=[],
        )

        os.mkdir(var.run_dir) # for this API-method run

        var.update(
            return_dir=os.path.join(var.run_dir, 'return'),
        )

        os.mkdir(var.return_dir) # for return input/output/logs etc.

        if var.debug:
            with open(os.path.join(var.run_dir, '#params'), 'w') as fh:
                json.dump(params.params, fh)
    
        # TODO document `run_dir` structure

        #
        ##
        ### obj
        ####
        #####


        # instantiate

        amp_mat = AmpliconMatrix(params['amplicon_matrix_upa']) 
        if 'row_attributemapping_ref' in amp_mat.obj:
            row_attrmap = AttributeMapping(amp_mat.obj['row_attributemapping_ref'], amp_mat)
        else:
            msg = (
                "Input AmpliconMatrix "
                "does not have a row AttributeMapping to assign PICRUSt2 functions to. "
                "To create one, import the amplicon metadata as an Attribute Mapping first, "
                "then select it when importing the Amplicon Matrix"
            )
            logging.warning(msg)
            var.warnings.append(msg)



        # validate input data

        amp_mat.validate_amplicon_abundance_data()


        # generate input files
        
        seq_flpth = os.path.join(var.return_dir, 'study_seqs.fna')
        seq_abundance_table_flpth = os.path.join(var.return_dir, 'study_seqs.tsv') 

        amp_mat.to_fasta(seq_flpth)
        amp_mat.to_seq_abundance_table(seq_abundance_table_flpth)


        # objs should be app globals
        var.amp_mat = amp_mat


        #
        ##
        ### args
        ####
        #####
        
        
        var.out_dir = os.path.join(var.return_dir, 'PICRUSt2_output')
        log_flpth = os.path.join(var.return_dir, 'cmd_log.txt')


        cmd_pipeline = ' '.join([
            'set -o pipefail &&',
            'source activate picrust2 &&',
            'picrust2_pipeline.py',
            '-s', seq_flpth,
            '-i', seq_abundance_table_flpth,
            '-o', var.out_dir,
            '--per_sequence_contrib',
            '-p 4',
            '|& tee', log_flpth,
        ])
        
    

        cmd_description = ' \\\n'.join([
            'cd %s &&' % var.out_dir,
            'source activate picrust2 &&',
            'add_descriptions.py -i EC_metagenome_out/pred_metagenome_unstrat.tsv.gz -m EC',
            '                    -o EC_metagenome_out/pred_metagenome_unstrat_descrip.tsv.gz',
            '&&',
            'add_descriptions.py -i KO_metagenome_out/pred_metagenome_unstrat.tsv.gz -m KO',
            '                    -o KO_metagenome_out/pred_metagenome_unstrat_descrip.tsv.gz',
            '&&',
            'add_descriptions.py -i pathways_out/path_abun_unstrat.tsv.gz -m METACYC',
            '                    -o pathways_out/path_abun_unstrat_descrip.tsv.gz'
        ])



        #
        ##
        ### run
        ####
        #####

        run_check(cmd_pipeline)
        run_check(cmd_description)



        #
        ##
        ### update/save Amplicon workflow objects 
        ####
        #####


        path_abun_predictions_tsv_gz_flpth = os.path.join(
            var.out_dir, 'pathways_out/path_abun_predictions.tsv.gz') 

        attribute = 'PICRUSt2 MetaCyc Pathway Predictions'
        source = 'kb_PICRUSt2/run_picrust2_pipeline'

        # if row AttributeMapping, 
        # update that and referencing objs
        if amp_mat.row_attrmap_upa is not None: 

            # update row AttributeMapping with traits
            id2attr = OutfileWrangler.parse_picrust2_traits(path_abun_predictions_tsv_gz_flpth)
            ind = row_attrmap.get_attribute_slot_warn(attribute, source)
            row_attrmap.map_update_attribute(ind, id2attr)
            row_attrmap_upa_new = row_attrmap.save()

            # update AmpliconMatrix which references row AttributeMapping
            amp_mat.obj['row_attributemapping_ref'] = row_attrmap_upa_new
            amp_mat_upa_new = amp_mat.save(name=params.getd('output_name'))         

            var.objects_created.extend([
                {'ref': row_attrmap_upa_new, 'description': 'Added or updated attribute `%s`' % attribute}, 
                {'ref': amp_mat_upa_new, 'description': 'Updated row AttributeMapping reference'},
            ])

    
       

        #
        ##
        ### prepare dir to give FPU decompressed TSVs
        ####
        #####


        tsv_dir = os.path.join(var.shared_folder, 'kbp2_decompressed_tsv_dir_' + str(uuid.uuid4()))
        os.mkdir(tsv_dir)

        logging.info('Preparing TSV directory %s' % tsv_dir)

        dprint('touch %s' % os.path.join(tsv_dir, '#' + amp_mat.name)) # debug annotation
        for tsvgz_relflpth, tsv_flnm in var.tsvgzRelFlpth2TsvFlnm.items(): # output dir to new dir
            gunzip_to(
                os.path.join(var.out_dir, tsvgz_relflpth),
                os.path.join(tsv_dir, tsv_flnm)
            )

        tsv_flpth_l = [os.path.join(tsv_dir, tsv_flnm) for tsv_flnm in var.tsvgzRelFlpth2TsvFlnm.values()] # new, decompressed TSVs
        

        # look at TSVs 
        dprint(
            'ls -lh %s' % tsv_dir,
            'file -i %s/*' % tsv_dir, 
            run='cli'
        )


        #
        ##
        ### save FunctionalProfile objects
        ####
        #####

        logging.info('Starting FunctionalProfile business')


        if var.debug:
            FP_amp_mat_ref = params['amplicon_matrix_upa']  # this makes mocking more flexible in case something makes a fake UPA
        else:
            FP_amp_mat_ref = amp_mat_upa_new # this AmpliconMatrix is new one with new AttributeMapping

        """
        if params.getd('create_sample_fps') is True and 'sample_set_ref' not in amp_mat.obj: # TODO why?
            msg = (
                'Sorry, input AmpliconMatrix %s does not have a SampleSet reference '
                'and so creating community FunctionalProfiles is prohibited. '
                'Please see importers to link a SampleSet'
                % amp_mat.name
            )
            logging.warning(msg)
            var.warnings.append(msg)
        """

        ## Community FPs
        if params.getd('create_sample_fps') is True :

            # Check nothing dropped (debug)
            for tsv_flpth in tsv_flpth_l[:3]:
                OutfileWrangler.check_dropped_sample_ids(tsv_flpth, amp_mat)


            var.objects_created.append(dict(
                ref=var.fpu.import_func_profile(dict(
                    workspace_id=var.params['workspace_id'],
                    func_profile_obj_name='%s.PICRUSt2_path_abun_unstrat' % amp_mat.name,
                    original_matrix_ref=FP_amp_mat_ref,
                    profile_file_path=tsv_flpth_l[0],
                    profile_type='mg',
                    profile_category='community',
                    data_epistemology='predicted',
                    epistemology_method='PICRUSt2',
                    description='Pathway abundance, MetaCyc vs. sample', # put these descriptions in config so i can use them in heatmap titles (?) TODO
                ))['func_profile_ref'],
                description='Pathway abundance, MetaCyc vs. sample',
            ))

            var.objects_created.append(dict(
                ref=var.fpu.import_func_profile(dict(
                    workspace_id=var.params['workspace_id'],
                    func_profile_obj_name='%s.PICRUSt2_EC_pred_metagenome_unstrat' % amp_mat.name,
                    original_matrix_ref=FP_amp_mat_ref,
                    profile_file_path=tsv_flpth_l[1],
                    profile_type='mg',
                    profile_category='community',
                    data_epistemology='predicted',
                    epistemology_method='PICRUSt2',
                    description='Gene family abundance, EC vs. sample',
                ))['func_profile_ref'],
                description='Gene family abundance, EC vs. sample',
            ))

            var.objects_created.append(dict(
                ref=var.fpu.import_func_profile(dict(
                    workspace_id=var.params['workspace_id'],
                    func_profile_obj_name='%s.PICRUSt2_KO_pred_metagenome_unstrat' % amp_mat.name,
                    original_matrix_ref=FP_amp_mat_ref,
                    profile_file_path=tsv_flpth_l[2],
                    profile_type='mg',
                    profile_category='community',
                    data_epistemology='predicted',
                    epistemology_method='PICRUSt2',
                    description='Gene family abundance, KO vs. sample',
                ))['func_profile_ref'],
                description='Gene family abundance, KO vs. sample',
            ))


        ## Organism FPs ##
        if params.getd('create_amplicon_fps') is True:

            # Check dropped amplicons are the unaligned/distant ones (debug)
            for tsv_flpth in tsv_flpth_l[3:]:
                OutfileWrangler.check_dropped_amplicon_ids(tsv_flpth, amp_mat)

            var.objects_created.append(dict(
                ref=var.fpu.import_func_profile(dict(
                    workspace_id=var.params['workspace_id'],
                    func_profile_obj_name='%s.PICRUSt2_path_abun_predictions' % amp_mat.name,
                    original_matrix_ref=FP_amp_mat_ref,
                    profile_file_path=tsv_flpth_l[3],
                    profile_type='amplicon',
                    profile_category='organism',
                    data_epistemology='predicted',
                    epistemology_method='PICRUSt2',
                    description='Pathway abundance, amplicon vs. MetaCyc',
                ))['func_profile_ref'],
                description='Pathway abundance, amplicon vs. MetaCyc',
            ))

            var.objects_created.append(dict(
                ref=var.fpu.import_func_profile(dict(
                    workspace_id=var.params['workspace_id'],
                    func_profile_obj_name='%s.PICRUSt2_EC_predicted' % amp_mat.name,
                    original_matrix_ref=FP_amp_mat_ref,
                    profile_file_path=tsv_flpth_l[4],
                    profile_type='amplicon',
                    profile_category='organism',
                    data_epistemology='predicted',
                    epistemology_method='PICRUSt2',
                    description='Gene family abundance, amplicon vs. EC',
                ))['func_profile_ref'],
                description='Gene family abundance, amplicon vs. EC',
            ))
     
            var.objects_created.append(dict(
                ref=var.fpu.import_func_profile(dict(
                    workspace_id=var.params['workspace_id'],
                    func_profile_obj_name='%s.PICRUSt2_KO_predicted' % amp_mat.name,
                    original_matrix_ref=FP_amp_mat_ref,
                    profile_file_path=tsv_flpth_l[5],
                    profile_type='amplicon',
                    profile_category='organism',
                    data_epistemology='predicted',
                    epistemology_method='PICRUSt2',
                    description='Gene family abundance, amplicon vs. KO',
                ))['func_profile_ref'],
                description='Gene family abundance, amplicon vs. KO',
            ))




        #
        ##
        ### html report w/ heatmaps
        ####
        #####

        logging.info('Beginning report business')


        ##
        ## report

        var.report_dir = os.path.join(var.run_dir, 'report')

        t0 = time.time()
        report_html_flpth = HTMLReportWriter(
                [cmd_pipeline, cmd_description], 
                tsv_flpth_l,
                var.report_dir
        ).write()
        t = time.time() - t0

        dprint('Done with all %d heatmaps and report. Took %.1f min' % (len(tsv_flpth_l), (t/60)))

        html_links = [{
            'path': var.report_dir,
            'name': os.path.basename(report_html_flpth),
        }]



        #
        ##
        ### return files
        ####
        #####


        file_links = [{
                'path': var.return_dir, 
                'name': 'PICRUSt2_results.zip', 
                'description': 'Input, output, cmd, intermediate files, log'
        }]
       
        params_report = {
            'warnings': var.warnings,
            'objects_created': var.objects_created,
            'file_links': file_links,
            'html_links': html_links,
            'direct_html_link_index': 0,
            'report_object_name': 'kb_PICRUSt2_report',
            'workspace_name': params['workspace_name'],
        }

        var.params_report = params_report

        report = var.kbr.create_extended_report(params_report)

        output = {
            'report_name': report['name'],
            'report_ref': report['ref'],
        }

        #END run_picrust2_pipeline

        # At some point might do deeper type checking...
        if not isinstance(output, dict):
            raise ValueError('Method run_picrust2_pipeline return value ' +
                             'output is not type dict as required.')
        # return the results
        return [output]
    def status(self, ctx):
        #BEGIN_STATUS
        returnVal = {'state': "OK",
                     'message': "",
                     'version': self.VERSION,
                     'git_url': self.GIT_URL,
                     'git_commit_hash': self.GIT_COMMIT_HASH}
        #END_STATUS
        return [returnVal]
