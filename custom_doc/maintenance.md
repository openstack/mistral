This section describes the following maintenace information including the database cleanup.

# Database Cleanup

The database cleanup information is given below.

## Execution Expiration Policy

For detailed information about the execution expiration policy, refer to the _Official Mistral Documentation_ at [https://docs.openstack.org/mistral/latest/user/main_features.html#execution-expiration-policy](https://docs.openstack.org/mistral/latest/user/main_features.html#execution-expiration-policy).

You can apply these options only if Mistral version is greater than `v5.2.0_nc3`.

<!-- #GFCFilterMarkerStart# -->
For more information on applying parameters to the custom Mistral configuration, see [Mistral Configuration Parameters Customization](user.md##mistral-configuration-parameters-customization).
<!-- #GFCFilterMarkerEnd# -->

The following are the details about the parameters:

`evaluation_interval` - How often the executions are evaluated (`in minutes`). 
For example, with value "120," the interval is 2 hours (every 2 hours). Note 
that only final state executions are removed: (`SUCCESS` / `ERROR` / `CANCELLED`).

`older_than` - Evaluate from which time executions should be removed (`in minutes`). For example, 
when older_than = 60, remove **all executions** that finished 60 minutes ago or 
more. The minimum value is 1.

`max_finished_executions` - The maximum number of finished workflow executions 
to be stored. For example, when `max_finished_executions = 100` only the latest 100
finished executions are preserved. Even the unexpired executions 
are eligible for deletion in order to decrease the number of executions in the database. 
The default value is 0. If it is set to 0, no maximum constraint is applied.

`batch_size` - Size of the batch of expired executions to be deleted. The default 
value is 0. If it is set to 0, the size of the batch is the total number of expired 
executions that are going to be deleted.

Example:

```
[execution_expiration_policy]
evaluation_interval = 120  # 2 hours
older_than = 10080  # 1 week
max_finished_executions = 500
batch_size = 10
```

## Manual Database Cleanup

**Note**: Mistral must not be under load during the following operations.

You can delete using two kinds of operation:

`DELETE` - If you want remove by condition. For example, remove by date:

```sql
DELETE FROM workflow_executions_v2 
WHERE updated_at < '2018-04-13 16:55:45'::timestamp 
      AND state IN ('SUCCESS', 'ERROR', 'CANCELLED');
``` 

`TRUNCATE` - If you want to remove all executions, tasks, and actions:

```sql
TRUNCATE workflow_executions_v2 CASCADE;
```

After tuples deletion you should execute _vacuum full_ to reclaim a disk space. 

For example:

```sql
VACUUM (FULL) workflow_executions_v2;
VACUUM (FULL) task_executions_v2;
VACUUM (FULL) action_executions_v2;
```

For more information on _vacuum full_, refer to the _Official PostgreSQL Documentation_ at [https://www.postgresql.org/docs/9.6/static/sql-vacuum.html](https://www.postgresql.org/docs/9.6/static/sql-vacuum.html).
