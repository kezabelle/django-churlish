

class Occurs(object):
    """
    Can count the number of times a string occurs in a column's contents
    
    In Python, that's:
    len(column) - len(column.replace(needle, '')) / len(needle)
    
    In SQL, it's something like:
    length(column) - LENGTH(REPLACE(column, needle, '')) / LENGTH(needle) AS alias
    """
    pass
