select *
from {{ ref('fct_ev_opportunities') }}
where expected_value < {{ var('ev_threshold') }}
    or book_count < {{ var('min_books') }}
