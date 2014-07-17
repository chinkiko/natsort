# -*- coding: utf-8 -*-
"""
Natsort can sort strings with numbers in a natural order.
It provides the natsorted function to sort strings with
arbitrary numbers.

You can mix types with natsorted.  This can get around the new
'unorderable types' issue with Python 3. Natsort will recursively
descend into lists of lists so you can sort by the sublist contents.

See the README or the natsort homepage for more details.

"""

from __future__ import print_function, division, unicode_literals, absolute_import

import re
import sys
from operator import itemgetter
from functools import partial
from itertools import islice
from warnings import warn

from .py23compat import u_format, py23_basestring, py23_str, \
                        py23_range, py23_zip

__doc__ = u_format(__doc__) # Make sure the doctest works for either
                            # python2 or python3

# The regex that locates floats
float_sign_exp_re = re.compile(r'([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)')
float_nosign_exp_re = re.compile(r'(\d*\.?\d+(?:[eE][-+]?\d+)?)')
float_sign_noexp_re = re.compile(r'([-+]?\d*\.?\d+)')
float_nosign_noexp_re = re.compile(r'(\d*\.?\d+)')
# Integer regexes
int_nosign_re = re.compile(r'(\d+)')
int_sign_re = re.compile(r'([-+]?\d+)')
# This dict will help select the correct regex and number conversion function.
regex_and_num_function_chooser = {
    (float, True,  True)  : (float_sign_exp_re,     float),
    (float, True,  False) : (float_sign_noexp_re,   float),
    (float, False, True)  : (float_nosign_exp_re,   float),
    (float, False, False) : (float_nosign_noexp_re, float),
    (int,   True,  True)  : (int_sign_re,   int),
    (int,   True,  False) : (int_sign_re,   int),
    (int,   False, True)  : (int_nosign_re, int),
    (int,   False, False) : (int_nosign_re, int),
    (None,  True,  True)  : (int_nosign_re, int),
    (None,  True,  False) : (int_nosign_re, int),
    (None,  False, True)  : (int_nosign_re, int),
    (None,  False, False) : (int_nosign_re, int),
}

# Number types.  I have to use set([...]) and not {...}
# because I am supporting Python 2.6.
number_types = set([float, int])


def _number_finder(s, regex, numconv, py3_safe):
    """Helper to split numbers"""

    # Split the input string by numbers.
    # If there are no splits, return now.
    # If the input is not a string, ValueError is raised.
    s = regex.split(s)
    if len(s) == 1:
        return tuple(s)

    # Now convert the numbers to numbers, and leave strings as strings.
    # Remove empty strings from the list.
    # Profiling showed that using regex here is much faster than
    # try/except with the numconv function.
    r = regex.match
    s = [numconv(x) if r(x) else x for x in s if x]

    # If the list begins with a number, lead with an empty string.
    # This is used to get around the "unorderable types" issue.
    # The most common case will be a string at the front of the
    # list, and in that case the try/except method is faster than
    # using isinstance. This was chosen at the expense of the less
    # common case of a number being at the front of the list.
    try:
        s[0][0] # str supports indexing, but not numbers
    except TypeError:
        s = [''] + s

    # The _py3_safe function inserts "" between numbers in the list,
    # and is used to get around "unorderable types" in complex cases.
    # It is a separate function that needs to be requested specifically
    # because it is expensive to call.
    return  _py3_safe(s) if py3_safe else s


def _py3_safe(parsed_list):
    """Insert '' between two numbers."""
    if len(parsed_list) < 2:
        return parsed_list
    else:
        new_list = [parsed_list[0]]
        nl_append = new_list.append
        ntypes = number_types
        for before, after in py23_zip(islice(parsed_list, 0, len(parsed_list)-1),
                                      islice(parsed_list, 1, None)):
            # I realize that isinstance is favored over type, but
            # in this case type is SO MUCH FASTER than isinstance!!
            if type(before) in ntypes and type(after) in ntypes:
                nl_append("")
            nl_append(after)
        return new_list


def _natsort_key(val, key=None, number_type=float, signed=True, exp=True, py3_safe=False):
    """\
    Key to sort strings and numbers naturally.

    It works by separating out the numbers from the strings. This function for
    internal use only. See the natsort_keygen documentation for details of each
    parameter.

    Parameters
    ----------
    val : {str, unicode}
    key : callable, optional
    number_type : {None, float, int}, optional
    signed : {True, False}, optional
    exp : {True, False}, optional
    py3_safe : {True, False}, optional

    Returns
    -------
    out : tuple
        The modified value with numbers extracted.

    """
    
    # Convert the arguments to the proper input tuple
    inp_options = (number_type, signed, exp)
    try:
        regex, num_function = regex_and_num_function_chooser[inp_options]
    except KeyError:
        # Report errors properly
        if number_type not in (float, int) and number_type is not None:
            raise ValueError("_natsort_key: 'number_type' "
                             "parameter '{0}' invalid".format(py23_str(number_type)))
        elif signed not in (True, False):
            raise ValueError("_natsort_key: 'signed' "
                             "parameter '{0}' invalid".format(py23_str(signed)))
        elif exp not in (True, False):
            raise ValueError("_natsort_key: 'exp' "
                             "parameter '{0}' invalid".format(py23_str(exp)))
    else:
        # Apply key if needed.
        if key is not None:
            val = key(val)
        # Assume the input are strings, which is the most common case.
        try:
            return tuple(_number_finder(val, regex, num_function, py3_safe))
        except TypeError:
            # If not strings, assume it is an iterable that must
            # be parsed recursively. Do not apply the key recursively.
            try:
                return tuple([_natsort_key(x, None, number_type, signed,
                                              exp, py3_safe) for x in val])
            # If there is still an error, it must be a number.
            # Return as-is, with a leading empty string.
            # Waiting for two raised errors instead of calling
            # isinstance at the opening of the function is slower
            # for numbers but much faster for strings, and since
            # numbers are not a common input to natsort this is
            # an acceptable sacrifice.
            except TypeError:
                return ('', val,)


@u_format
def natsort_key(val, key=None, number_type=float, signed=True, exp=True, py3_safe=False):
    """\
    Key to sort strings and numbers naturally.

    Key to sort strings and numbers naturally, not lexicographically.
    It is designed for use in passing to the 'sorted' builtin or
    'sort' attribute of lists.

    .. note:: Depreciation Notice (3.4.0)
              This function remains in the publicly exposed API for
              backwards-compatibility reasons, but future development
              should use the newer `natsort_keygen` function. It is
              planned to remove this from the public API in natsort
              version 4.0.0.  A DeprecationWarning will be raised
              via the warnings module; set warnings.simplefilter("always")
              to raise them to see if your code will work in version
              4.0.0.

    Parameters
    ----------
    val : {{str, unicode}}
        The value used by the sorting algorithm

    key : callable, optional
        A key used to manipulate the input value before parsing for
        numbers. It is **not** applied recursively.
        It should accept a single argument and return a single value.

    number_type : {{None, float, int}}, optional
        The types of number to sort on: `float` searches for floating
        point numbers, `int` searches for integers, and `None `searches
        for digits (like integers but does not take into account
        negative sign). `None` is a shortcut for `number_type = int`
        and `signed = False`.

    signed : {{True, False}}, optional
        By default a '+' or '-' before a number is taken to be the sign
        of the number. If `signed` is `False`, any '+' or '-' will not
        be considered to be part of the number, but as part part of the
        string.

    exp : {{True, False}}, optional
        This option only applies to `number_type = float`.  If
        `exp = True`, a string like "3.5e5" will be interpreted as
        350000, i.e. the exponential part is considered to be part of
        the number. If `exp = False`, "3.5e5" is interpreted as
        ``(3.5, "e", 5)``. The default behavior is `exp = True`.

    py3_safe : {{True, False}}, optional
        This will make the string parsing algorithm be more careful by
        placing an empty string between two adjacent numbers after the
        parsing algorithm. This will prevent the "unorderable types"
        error.

    Returns
    -------
    out : tuple
        The modified value with numbers extracted.

    See Also
    --------
    natsort_keygen : Generates a properly wrapped `natsort_key`.

    Examples
    --------
    Using natsort_key is just like any other sorting key in python::

        >>> a = ['num3', 'num5', 'num2']
        >>> a.sort(key=natsort_key)
        >>> a
        [{u}'num2', {u}'num3', {u}'num5']

    It works by separating out the numbers from the strings::

        >>> natsort_key('num2')
        ({u}'num', 2.0)

    If you need to call natsort_key with the number_type argument, or get a
    special attribute or item of each element of the sequence, please use
    the `natsort_keygen` function.  Actually, please just use the
    `natsort_keygen` function.

    Notes
    -----
    Iterables are parsed recursively so you can sort lists of lists::

        >>> natsort_key(('a1', 'a10'))
        (({u}'a', 1.0), ({u}'a', 10.0))

    Strings that lead with a number get an empty string at the front of the
    tuple. This is designed to get around the "unorderable types" issue of
    Python3::

        >>> natsort_key('15a')
        ({u}'', 15.0, {u}'a')

    You can give bare numbers, too::

        >>> natsort_key(10)
        ({u}'', 10)

    If you have a case where one of your string has two numbers in a row,
    you can turn on the "py3_safe" option to try to add a "" between sets
    of two numbers::

        >>> natsort_key('43h7+3', py3_safe=True)
        ({u}'', 43.0, {u}'h', 7.0, {u}'', 3.0)

    """
    msg = "natsort_key is depreciated as of 3.4.0, please use natsort_keygen"
    warn(msg, DeprecationWarning)
    return _natsort_key(val, key, number_type, signed, exp, py3_safe)


@u_format
def natsort_keygen(key=None, number_type=float, signed=True, exp=True, py3_safe=False):
    """\
    Generate a key to sort strings and numbers naturally.

    Generate a key to sort strings and numbers naturally,
    not lexicographically. This key is designed for use as the
    `key` argument to functions such as the `sorted` builtin.

    The user may customize the generated function with the
    arguments to `natsort_keygen`, including an optional
    `key` function which will be called before the `natsort_key`.

    Parameters
    ----------
    key : callable, optional
        A key used to manipulate the input value before parsing for
        numbers. It is **not** applied recursively.
        It should accept a single argument and return a single value.

    number_type : {{None, float, int}}, optional
        The types of number to sort on: `float` searches for floating
        point numbers, `int` searches for integers, and `None `searches
        for digits (like integers but does not take into account
        negative sign). `None` is a shortcut for `number_type = int`
        and `signed = False`.

    signed : {{True, False}}, optional
        By default a '+' or '-' before a number is taken to be the sign
        of the number. If `signed` is `False`, any '+' or '-' will not
        be considered to be part of the number, but as part part of the
        string.

    exp : {{True, False}}, optional
        This option only applies to `number_type = float`.  If
        `exp = True`, a string like "3.5e5" will be interpreted as
        350000, i.e. the exponential part is considered to be part of
        the number. If `exp = False`, "3.5e5" is interpreted as
        ``(3.5, "e", 5)``. The default behavior is `exp = True`.

    py3_safe : {{True, False}}, optional
        This will make the string parsing algorithm be more careful by
        placing an empty string between two adjacent numbers after the
        parsing algorithm. This will prevent the "unorderable types"
        error.

    Returns
    -------
    out : function
        A wrapped version of the `natsort_key` function that is
        suitable for passing as the `key` argument to functions
        such as `sorted`.

    Examples
    --------
    `natsort_keygen` is a convenient waynto create a custom key
    to sort lists in-place (for example). Calling with no objects
    will return a plain `natsort_key` instance::

        >>> a = ['num5.10', 'num-3', 'num5.3', 'num2']
        >>> b = a[:]
        >>> a.sort(key=natsort_key)
        >>> b.sort(key=natsort_keygen())
        >>> a == b
        True

    The power of `natsort_keygen` is when you want to want to pass
    arguments to the `natsort_key`.  Consider the following
    equivalent examples; which is more clear? ::

        >>> a = ['num5.10', 'num-3', 'num5.3', 'num2']
        >>> b = a[:]
        >>> a.sort(key=lambda x: natsort_key(x, key=lambda y: y.upper(), signed=False))
        >>> b.sort(key=natsort_keygen(key=lambda x: x.upper(), signed=False))
        >>> a == b
        True

    """
    return partial(_natsort_key, key=key,
                                 number_type=number_type,
                                 signed=signed,
                                 exp=exp,
                                 py3_safe=py3_safe)


@u_format
def natsorted(seq, key=None, number_type=float, signed=True, exp=True, reverse=False):
    """\
    Sorts a sequence naturally.

    Sorts a sequence naturally (alphabetically and numerically),
    not lexicographically. Returns a new copy of the sorted
    sequence as a list.

    Parameters
    ----------
    seq : iterable
        The sequence to sort.

    key : callable, optional
        A key used to determine how to sort each element of the sequence.
        It is **not** applied recursively.
        It should accept a single argument and return a single value.

    number_type : {{None, float, int}}, optional
        The types of number to sort on: `float` searches for floating
        point numbers, `int` searches for integers, and `None `searches
        for digits (like integers but does not take into account
        negative sign). `None` is a shortcut for `number_type = int`
        and `signed = False`.

    signed : {{True, False}}, optional
        By default a '+' or '-' before a number is taken to be the sign
        of the number. If `signed` is `False`, any '+' or '-' will not
        be considered to be part of the number, but as part part of the
        string.

    exp : {{True, False}}, optional
        This option only applies to `number_type = float`.  If
        `exp = True`, a string like "3.5e5" will be interpreted as
        350000, i.e. the exponential part is considered to be part of
        the number. If `exp = False`, "3.5e5" is interpreted as
        ``(3.5, "e", 5)``. The default behavior is `exp = True`.

    reverse : {{True, False}}, optional
        Return the list in reversed sorted order. The default is
        `False`.

    Returns
    -------
    out: list
        The sorted sequence.

    See Also
    --------
    versorted : A wrapper for ``natsorted(seq, number_type=None)``.
    index_natsorted : Returns the sorted indexes from `natsorted`.

    Examples
    --------
    Use `natsorted` just like the builtin `sorted`::

        >>> a = ['num3', 'num5', 'num2']
        >>> natsorted(a)
        [{u}'num2', {u}'num3', {u}'num5']

    """
    try:
        return sorted(seq, reverse=reverse,
                      key=natsort_keygen(key, number_type,
                                         signed, exp))
    except TypeError as e:
        # In the event of an unresolved "unorderable types" error
        # attempt to sort again, being careful to prevent this error.
        if 'unorderable types' in str(e):
            return sorted(seq, reverse=reverse,
                          key=natsort_keygen(key, number_type,
                                             signed, exp, True))
        else:
            # Re-raise if the problem was not "unorderable types"
            raise


@u_format
def versorted(seq, key=None, reverse=False):
    """\
    Convenience function to sort version numbers.

    Convenience function to sort version numbers. This is a wrapper
    around ``natsorted(seq, number_type=None)``.

    Parameters
    ----------
    seq : iterable
        The sequence to sort.

    key : callable, optional
        A key used to determine how to sort each element of the sequence.
        It is **not** applied recursively.
        It should accept a single argument and return a single value.

    reverse : {{True, False}}, optional
        Return the list in reversed sorted order. The default is
        `False`.

    Returns
    -------
    out : list
        The sorted sequence.

    See Also
    --------
    index_versorted : Returns the sorted indexes from `versorted`.

    Examples
    --------
    Use `versorted` just like the builtin `sorted`::

        >>> a = ['num4.0.2', 'num3.4.1', 'num3.4.2']
        >>> versorted(a)
        [{u}'num3.4.1', {u}'num3.4.2', {u}'num4.0.2']

    """
    return natsorted(seq, key, None, reverse=reverse)


@u_format
def index_natsorted(seq, key=None, number_type=float, signed=True, exp=True, reverse=False):
    """\
    Return the list of the indexes used to sort the input sequence.

    Sorts a sequence naturally, but returns a list of sorted the
    indexes and not the sorted list. This list of indexes can be
    used to sort multiple lists by the sorted order of the given
    sequence.

    Parameters
    ----------
    seq : iterable
        The sequence to sort.

    key : callable, optional
        A key used to determine how to sort each element of the sequence.
        It is **not** applied recursively.
        It should accept a single argument and return a single value.

    number_type : {{None, float, int}}, optional
        The types of number to sort on: `float` searches for floating
        point numbers, `int` searches for integers, and `None `searches
        for digits (like integers but does not take into account
        negative sign). `None` is a shortcut for `number_type = int`
        and `signed = False`.

    signed : {{True, False}}, optional
        By default a '+' or '-' before a number is taken to be the sign
        of the number. If `signed` is `False`, any '+' or '-' will not
        be considered to be part of the number, but as part part of the
        string.

    exp : {{True, False}}, optional
        This option only applies to `number_type = float`.  If
        `exp = True`, a string like "3.5e5" will be interpreted as
        350000, i.e. the exponential part is considered to be part of
        the number. If `exp = False`, "3.5e5" is interpreted as
        ``(3.5, "e", 5)``. The default behavior is `exp = True`.

    reverse : {{True, False}}, optional
        Return the list in reversed sorted order. The default is
        `False`.

    Returns
    -------
    out : tuple
        The ordered indexes of the sequence.

    See Also
    --------
    natsorted
    order_by_index

    Examples
    --------

    Use index_natsorted if you want to sort multiple lists by the
    sorted order of one list::

        >>> a = ['num3', 'num5', 'num2']
        >>> b = ['foo', 'bar', 'baz']
        >>> index = index_natsorted(a)
        >>> index
        [2, 0, 1]
        >>> # Sort both lists by the sort order of a
        >>> order_by_index(a, index)
        [{u}'num2', {u}'num3', {u}'num5']
        >>> order_by_index(b, index)
        [{u}'baz', {u}'foo', {u}'bar']

    """
    if key is None:
        newkey = itemgetter(1)
    else:
        newkey = lambda x : key(itemgetter(1)(x))
    # Pair the index and sequence together, then sort by element
    index_seq_pair = [[x, y] for x, y in enumerate(seq)]
    try:
        index_seq_pair.sort(reverse=reverse,
                            key=natsort_keygen(newkey, number_type,
                                               signed, exp))
    except TypeError as e:
        # In the event of an unresolved "unorderable types" error
        # attempt to sort again, being careful to prevent this error.
        if 'unorderable types' in str(e):
            index_seq_pair.sort(reverse=reverse,
                                key=natsort_keygen(newkey, number_type,
                                                   signed, exp, True))
        else:
            # Re-raise if the problem was not "unorderable types"
            raise
    return [x for x, _ in index_seq_pair]


@u_format
def index_versorted(seq, key=None, reverse=False):
    """\
    Return the list of the indexes used to sort the input sequence
    of version numbers.

    Sorts a sequence naturally, but returns a list of sorted the
    indexes and not the sorted list. This list of indexes can be
    used to sort multiple lists by the sorted order of the given
    sequence.

    This is a wrapper around ``index_natsorted(seq, number_type=None)``.

    Parameters
    ----------
    seq: iterable
        The sequence to sort.

    key: callable, optional
        A key used to determine how to sort each element of the sequence.
        It is **not** applied recursively.
        It should accept a single argument and return a single value.

    reverse : {{True, False}}, optional
        Return the list in reversed sorted order. The default is
        `False`.

    Returns
    -------
    out : tuple
        The ordered indexes of the sequence.

    See Also
    --------
    versorted
    order_by_index

    Examples
    --------
    Use `index_versorted` just like the builtin `sorted`::

        >>> a = ['num4.0.2', 'num3.4.1', 'num3.4.2']
        >>> index_versorted(a)
        [1, 2, 0]

    """
    return index_natsorted(seq, key, None, reverse=reverse)


@u_format
def order_by_index(seq, index, iter=False):
    """\
    Order a given sequence by an index sequence.
    
    The output of `index_natsorted` and `index_versorted` is a
    sequence of integers (index) that correspond to how its input
    sequence **would** be sorted. The idea is that this index can
    be used to reorder multiple sequences by the sorted order of the
    first sequence. This function is a convenient wrapper to
    apply this ordering to a sequence.
    
    Parameters
    ----------
    seq : iterable
        The sequence to order.
        
    index : iterable
        The sequence that indicates how to order `seq`.
        It should be the same length as `seq` and consist
        of integers only.
        
    iter : {{True, False}}, optional
        If `True`, the ordered sequence is returned as a
        generator expression; otherwise it is returned as a
        list. The default is `False`.
        
    Returns
    -------
    out : {{list, generator}}
        The sequence ordered by `index`, as a `list` or as a
        generator expression (depending on the value of `iter`).

    See Also
    --------
    index_natsorted
    index_versorted
    
    Examples
    --------

    `order_by_index` is a comvenience function that helps you apply
    the result of `index_natsorted` or `index_versorted`::

        >>> a = ['num3', 'num5', 'num2']
        >>> b = ['foo', 'bar', 'baz']
        >>> index = index_natsorted(a)
        >>> index
        [2, 0, 1]
        >>> # Sort both lists by the sort order of a
        >>> order_by_index(a, index)
        [{u}'num2', {u}'num3', {u}'num5']
        >>> order_by_index(b, index)
        [{u}'baz', {u}'foo', {u}'bar']

    """
    return (seq[i] for i in index) if iter else [seq[i] for i in index]

