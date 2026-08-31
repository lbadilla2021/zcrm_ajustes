def migrate(cr, version):
    cr.execute(
        """
        UPDATE crm_recorrido
           SET start_datetime = date::timestamp + interval '12 hours'
         WHERE start_datetime IS NULL
        """
    )
    cr.execute(
        """
        UPDATE crm_recorrido
           SET end_datetime = start_datetime
         WHERE state = 'done'
           AND end_datetime IS NULL
        """
    )
