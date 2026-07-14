"""Built-in LMDB browser plugin.

Owns kind ``lmdb-database`` (matched by ``folder_marker = "data.mdb"``).
Three views: ``keys`` (paginated key list), ``entry`` (one key's decoded
value), ``stats`` (env metadata). Domain plugins teach the reader about
their value schemas by calling ``metabrowser.lmdb_reader.register_value_decoder``.
"""
