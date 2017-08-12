import re
import nltk


def clean(text,word_to_id):

    unknown_token="UNK"
    sentence_start_token="START"
    sentence_end_token="END"

    # metas and punctuation (keeping hyphens)
    timestamps = "\d+:\d+:\d+(\.\d+)*"
    speakers = "S\d*:"
    metas = "\[.{5,24}\]"
    punctuation = "[\_\"\.\!\?\:]+"
    new_line = "\n"
    pattern = "|".join([timestamps,speakers,metas,punctuation,new_line])

    # numbers not part of a word like CO2, mp3, etc.
    numbers = "(?<!\w)\d+"

    line = text.decode("utf-8")

    # remove timestamps, speakers, metas, and punctuation. then lower and strip, then sub numbers
    cleaned = re.sub(pattern,"",line).lower().strip()
    sentence = re.sub(numbers,"N",cleaned)

    # was != "", but there were a number of sentences of just "s"
    sentence = "{} {} {}".format(sentence_start_token,sentence,sentence_end_token)

    # word tokenize
    word_tokenized = nltk.word_tokenize(sentence)

    out_sentence = [word_to_id[word] if word in word_to_id else unknown_token for word in word_tokenized]

    return out_sentence


