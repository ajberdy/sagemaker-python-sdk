# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
#     http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.
"""Repack model script for training jobs to inject entry points"""
from __future__ import absolute_import

import argparse
import os
import shutil
import tarfile
import tempfile

# Repack Model
# The following script is run via a training job which takes an existing model and a custom
# entry point script as arguments. The script creates a new model archive with the custom
# entry point in the "code" directory along with the existing model.  Subsequently, when the model
# is unpacked for inference, the custom entry point will be used.
# Reference: https://docs.aws.amazon.com/sagemaker/latest/dg/amazon-sagemaker-toolkits.html

# distutils.dir_util.copy_tree works way better than the half-baked
# shutil.copytree which bombs on previously existing target dirs...
# alas ... https://bugs.python.org/issue10948
# we'll go ahead and use the copy_tree function anyways because this
# repacking is some short-lived hackery, right??
from distutils.dir_util import copy_tree


def repack(inference_script, model_archive, dependencies=None, source_dir=None):
    """Repack custom dependencies and code into an existing model TAR archive

    Args:
        inference_script (str): The path to the custom entry point.
        model_archive (str): The name of the model TAR archive.
        dependencies (str): A space-delimited string of paths to custom dependencies.
        source_dir (str): The path to a custom source directory.
    """

    # the data directory contains a model archive generated by a previous training job
    data_directory = "/opt/ml/input/data/training"
    model_path = os.path.join(data_directory, model_archive)

    # create a temporary directory
    with tempfile.TemporaryDirectory() as tmp:
        local_path = os.path.join(tmp, "local.tar.gz")
        # copy the previous training job's model archive to the temporary directory
        shutil.copy2(model_path, local_path)
        src_dir = os.path.join(tmp, "src")
        # create the "code" directory which will contain the inference script
        code_dir = os.path.join(src_dir, "code")
        os.makedirs(code_dir)
        # extract the contents of the previous training job's model archive to the "src"
        # directory of this training job
        with tarfile.open(name=local_path, mode="r:gz") as tf:
            tf.extractall(path=src_dir)

        # copy the custom inference script to code/
        entry_point = os.path.join("/opt/ml/code", inference_script)
        shutil.copy2(entry_point, os.path.join(src_dir, "code", inference_script))

        # copy source_dir to code/
        if source_dir:
            if os.path.exists(code_dir):
                shutil.rmtree(code_dir)
                shutil.copytree(source_dir, code_dir)

        # copy any dependencies to code/lib/
        if dependencies:
            for dependency in dependencies.split(" "):
                actual_dependency_path = os.path.join("/opt/ml/code", dependency)
                lib_dir = os.path.join(code_dir, "lib")
                if not os.path.exists(lib_dir):
                    os.mkdir(lib_dir)
                if os.path.isdir(actual_dependency_path):
                    shutil.copytree(
                        actual_dependency_path,
                        os.path.join(lib_dir, os.path.basename(actual_dependency_path)),
                    )
                else:
                    shutil.copy2(actual_dependency_path, lib_dir)

        # copy the "src" dir, which includes the previous training job's model and the
        # custom inference script, to the output of this training job
        copy_tree(src_dir, "/opt/ml/model")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inference_script", type=str, default="inference.py")
    parser.add_argument("--dependencies", type=str, default=None)
    parser.add_argument("--source_dir", type=str, default=None)
    parser.add_argument("--model_archive", type=str, default="model.tar.gz")
    args, extra = parser.parse_known_args()
    repack(
        inference_script=args.inference_script,
        dependencies=args.dependencies,
        source_dir=args.source_dir,
        model_archive=args.model_archive,
    )
