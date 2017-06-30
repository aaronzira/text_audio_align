
def num_to_text(number):
    """Convert string representations of positive integers
    to word forms of those numbers"""

    number = str(number)
    length = len(number)
    if length > 15:
        return "lots and lots"

    # base cases
    two_digit = {"11":"eleven","12":"twelve","13":"thirteen",
            "15":"fifteen","18":"eighteen"}
    units = {k:v for k,v in zip(range(10),
        ["zero","one","two","three","four",
         "five","six","seven","eight","nine"])}
    tens = {k:v for k,v in zip(range(10),
        [" ","ten","twenty","thirty","forty",
         "fifty","sixty","seventy","eighty","ninety"])}
    large = {k:v for k,v in zip(range(4),
        ["thousand","million","billion","trillion"])}

    # if it starts with a 0, just print the digits
    if number[0] == "0":
        digits = "zero"
        for digit in number[1:]:
            digits = " ".join((digits,units[int(digit)]))
        return digits

    # single digits. zero is nothing to allow for separating 1st/2nd/3rd from larger numbers
    if length < 2:
        unit = int(number)
        if unit == 0:
            return ""
        return units[unit]

    # double digits
    if length < 3:
        try:
            return two_digit[number]
        except:
            if number[-1]=='0':
                return tens[int(number[0])]
            if number[0]=='1':
                return "{}{}".format(units[int(number[-1])],'teen')
            return "{} {}".format(tens[int(number[-2])],
                                  num_to_text(int(number[-1:])))
    # triple digits
    if length < 4:
        if number[-2:]=='00':
            return "{} hundred".format(units[int(number[-3])])
        return "{} hundred {}".format(units[int(number[-3])],
                                      num_to_text(int(number[-2:])))

    # get number of thousands (groups of 3) and 'remainder'
    # that doesn't make a full group
    groups = length//3-1
    first = length%3

    prefix = ""
    if first > 0:
        prefix = '{} {}'.format(num_to_text(number[:first]),large[groups])
        number = number[first:]

    # start with largest unit and iterate down
    for g in range(groups,0,-1):
        current_chunk = int(number[:3])
        next_chunk = number[3:]
        if current_chunk==0:
            continue
        prefix = '{} {}'.format(prefix,
                                '{} {}'.format(num_to_text(current_chunk),
                                               large[g-1]))
        number = next_chunk

    result = '{} {}'.format(prefix,num_to_text(int(number)))

    return result


