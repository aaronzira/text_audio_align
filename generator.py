import os
import re
import sys
import nltk
import itertools
import numpy as np

from unidecode import unidecode

from num2text import num_to_text

def data_generator(file_path,shuffle,vocabulary_size,train_size,test_size):
    """Generate train/test/val splits of one processed sentence per line
    for use as language model training data.
    """

    # python 3.5
    assert float(sys.version.split("|")[0].split()[0][:3]) == 3.5
    vocabulary_size = int(vocabulary_size)
    train_size = float(train_size)
    test_size = float(test_size)
    options = ["NOT ",""]
    print("Sentences will {}be shuffled".format(options[shuffle]))
    print("Test size: {:.2%}".format(test_size))
    print("Train size: {:.2%}".format(train_size))

    random_state = 42
    unknown_token = "UNK"

    # metas, punctuation
    timestamps = "\d+:\d+:\d+(\.\d+)*"
    speakers = "S\d*:"
    metas = "\[[^\[]{,24}\]"
    punctuation = "[\"\.\,\!\?\:\;\-\#\*\/]+"

    re_pattern = re.compile("|".join([timestamps,speakers,metas,punctuation]))
    re_decimal  = re.compile("([0-9]+)\.([0-9]+)") # decimals
    re_url = re.compile("(?<! )\.([a-z]{2,4})") # URLs
    re_negative = re.compile(" \-(\d+)") # negative numbers
    re_and  = re.compile("\&")
    re_at = re.compile("\@")
    re_percent = re.compile("\%")
    re_plus = re.compile("\+")
    re_equals = re.compile("\=")
    re_exponent = re.compile("\^")
    re_degrees = re.compile("\°")
    # there will be a space even if '$25' is at the end of the sentence thanks to punctuation removal above
    re_currencies = re.compile("[\$\€\£\₹\¥](\d+) (?!thousand|million|billion|trillion)")
    re_alnum = re.compile("[^a-z ]")
    re_tens = re.compile("(twen|thir|for|fif|six|seven|eigh|nine)ty( *)s ")

    # list of individual cleaned sentences
    sentences = []

    for idx,txt_file in enumerate(os.listdir(file_path)):
        doc_sents = []
        with open(os.path.join(file_path,txt_file),"r") as f:
            for paragraph in f.readlines():
                for sentence in nltk.sent_tokenize(paragraph):

                    # get rid of sentences with blanks
                    if "_" in sentence:
                        continue

                    sentence = re_decimal.sub("\\1 point \\2", sentence) # decimals
                    sentence = re_url.sub(" dot \\1", sentence) # URLs
                    sentence = re_negative.sub(" minus \\1", sentence) # negative numbers
                    sentence = re_pattern.sub(" ", sentence).lower() # space in case it was connected to a word
                    sentence = re_and.sub(" and ", sentence)
                    sentence = re_at.sub(" at ", sentence)
                    sentence = re_percent.sub(" percent ", sentence)
                    sentence = re_plus.sub(" plus ", sentence)
                    sentence = re_equals.sub(" equals ", sentence)
                    sentence = re_exponent.sub(" to the ", sentence)
                    sentence = re_degrees.sub(" degrees ", sentence)
                    sentence = re_currencies.sub("\\1 dollars ", sentence)
                    numbers = re.findall("\d+",sentence)
                    for num in numbers:
                        sentence = sentence.replace(num, " {} ".format(num_to_text(num)), 1)
                    sentence = unidecode(sentence)
                    sentence = re_alnum.sub("",sentence)
                    sentence = re_tens.sub("\\1ties ", sentence)

                    doc_sents.append(sentence)

        sentences.extend([sent.split() for sent in doc_sents])

    # word frequencies
    word_freq = nltk.FreqDist(itertools.chain(*sentences))
    print("{} sentences".format(len(sentences)))
    print("{} unique tokens".format(len(word_freq.items())))

    # most common words
    print("Restricting vocabulary to top {} tokens...".format(vocabulary_size))
    vocab = word_freq.most_common(vocabulary_size-1)
    in_vocab = set([x[0] for x in vocab])
    in_vocab.add(unknown_token)

    print("The least frequent word is '{}' and appears {} times."
          .format(vocab[-1][0], vocab[-1][1]))

    # replace rare words with unknown token
    for i,sent in enumerate(sentences):
        sentences[i] = " ".join([w
                                  if w in in_vocab
                                  else unknown_token
                                  for w in sent])

    # shuffle sentenes
    if shuffle:
        np.random.seed(random_state)
        np.random.shuffle(sentences)

    # train/test/val split
    split_index1 = int(len(sentences)*train_size)
    split_index2 = split_index1+int(len(sentences)*test_size)

    with open("./train.txt","w") as out:
        for sentence in sentences[:split_index1]:
            try:
                out.write("{}\n".format(sentence))
            except UnicodeEncodeError:
                print("Trouble with: ",sentence)

    with open("./valid.txt","w") as out:
        for sentence in sentences[split_index1:split_index2]:
            try:
                out.write("{}\n".format(sentence))
            except UnicodeEncodeError:
                print("Trouble with: ",sentence)

    with open("./test.txt","w") as out:
        for sentence in sentences[split_index2:]:
            try:
                out.write("{}\n".format(sentence))
            except UnicodeEncodeError:
                print("Trouble with: ",sentence)
    return


if __name__ =='__main__':

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--files_dir',default=None,help='Directory of text files to read')
    parser.add_argument('--shuffle',dest='shuffle',action='store_true',help='Shuffle order of sentences')
    parser.add_argument('--vocab_size',default=10000,type=int,help='Maximum number of unique tokens')
    parser.add_argument('--train_size',default=.8,type=float,help='Training set ratio (val size is train_size - test_size)')
    parser.add_argument('--test_size',default=.1,type=float,help='Test set ratio (val size is train_size - test_size)')
    parser.set_defaults(shuffle=False)
    args = parser.parse_args()

    data_generator(file_path=args.files_dir,shuffle=args.shuffle,vocabulary_size=args.vocab_size,train_size=args.train_size,test_size=args.test_size)

