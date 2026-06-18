class PrimaryReplicaRouter:
    """
    A database router to route read operations to the read replica,
    and write operations to the primary database.
    """
    def db_for_read(self, model, **hints):
        """
        Reads go to the replica database unless running tests.
        """
        import sys
        if 'test' in sys.argv or any('pytest' in arg for arg in sys.argv):
            return 'default'
        return 'replica'

    def db_for_write(self, model, **hints):
        """
        Writes always go to primary.
        """
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations if a model in the primary or replica is involved.
        """
        db_set = {'default', 'replica'}
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        All non-auth models end up in this pool.
        Ensure that we only migrate the primary database.
        """
        if db == 'replica':
            return False
        return True
