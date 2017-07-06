# Dump of files related to text and audio alignment, language models, and ASR data generation/testing/prediction. 


## Aligner and manifest generator
Generate text and audio splits from strings successfully aligned by Gentle, and write a manifest file of the generated files.

### aligner

with asr_data_gen.py and aligner.py moved to /PATH/TO/gentle/,
```
$ cd gentle
$ python asr_data_gen.py FILE_ID
```

### manifest generator
- to be used with [pytorch DS2](https://github.com/SeanNaren/deepspeech.pytorch)
```
$ python pytorch_manifest.py (optional: --files_dir /PATH/TO/WAV_AND_TXT/DIRS/ --out_file /PATH/TO/MANIFEST_FILE/)
```
