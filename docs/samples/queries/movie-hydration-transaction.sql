BEGIN;


-- Statement 1: upsert people

INSERT INTO people (tmdb_id, name, known_for_department, tmdb_profile_path)
VALUES ($1, $2, $3, $4)
ON CONFLICT (tmdb_id)
DO UPDATE SET
    name = excluded.name,
    known_for_department = excluded.known_for_department,
    tmdb_profile_path = excluded.tmdb_profile_path
WHERE (name, known_for_department, tmdb_profile_path)
IS DISTINCT FROM (
    excluded.name, excluded.known_for_department, excluded.tmdb_profile_path
);


-- Statement 2: upsert movies

INSERT INTO movies (tmdb_id, title, overview, tmdb_poster_path, release_date)
SELECT DISTINCT ON (m.id)
    m.id,
    m.title,
    m.overview,
    m.poster_path,
    m.release_date
FROM
    jsonb_to_recordset($5::jsonb)
        AS m (
            id bigint,
            title text,
            overview text,
            poster_path text,
            release_date date
        )
ORDER BY m.id
ON CONFLICT (tmdb_id) DO UPDATE
    SET
        title = excluded.title,
        overview = excluded.overview,
        tmdb_poster_path = excluded.tmdb_poster_path,
        release_date = excluded.release_date
    WHERE (
        movies.title,
        movies.overview,
        movies.tmdb_poster_path,
        movies.release_date
    )
    IS DISTINCT FROM (
        excluded.title,
        excluded.overview,
        excluded.tmdb_poster_path,
        excluded.release_date
    );


-- Statement 3: upsert credits

INSERT INTO credits (
    tmdb_id, movie_id, person_id, credit_type, credit_character, credit_order
)

SELECT
    c.credit_id,
    m.id AS movie_id,
    p.id AS person_id,
    c.credit_type,
    c.character,
    c.order
FROM
    jsonb_to_recordset($5::jsonb)
        AS c (
            credit_id text,
            credit_type text,
            id bigint,
            person_id bigint,
            character text,
            order int
        )
INNER JOIN movies AS m ON c.id = m.tmdb_id
INNER JOIN people AS p ON c.person_id = p.tmdb_id
ON CONFLICT (tmdb_id) DO UPDATE
    SET
        credit_type = excluded.credit_type,
        credit_character = excluded.credit_character,
        credit_order = excluded.credit_order
    WHERE (credits.credit_type, credits.credit_character, credits.credit_order)
    IS DISTINCT FROM (
        excluded.credit_type, excluded.credit_character, excluded.credit_order
    );


-- Statement 4: update last hydration timestamp

UPDATE people
SET tmdb_last_movies_hydration = now()
WHERE tmdb_id = $1;

COMMIT;
