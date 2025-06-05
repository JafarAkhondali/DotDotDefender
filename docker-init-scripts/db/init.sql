USE proj
create table progress
(
    id                   int auto_increment
        primary key,
    project_name         varchar(256)                       not null,
    stars_count          int      default 0                 null,
    step                 tinyint  default 0                 null,
    file_github_url      varchar(300)                       null,
    downloaded_file_name varchar(1000)                      null,
    is_paused            tinyint  default 0                 null,
    pause_reason         tinyint  default 0                 null,
    stuff_times          text                               null,
    semgrep_out          longtext                           null,
    is_local             tinyint  default 0                 null,
    is_vulnerable_to_dos tinyint  default 0                 null,
    vector_string        varchar(512)                       null comment 'CVSS Score Vector String',
    base_score           decimal(10, 5)                     null comment 'CVSS base score',
    severity             varchar(64)                        null comment 'CVSS Score severity',
    poc                  varchar(2048)                      null,
    run_method           varchar(128)                       null,
    llm_try_count        int                                null,
    created_at           datetime default CURRENT_TIMESTAMP null,
    updated_at           datetime default CURRENT_TIMESTAMP null,
    exit_code            int                                null,
    pull_request_link    varchar(512)                       null,
    first_appeared_at    date                               null,
    is_maintained        tinyint                            null,
    constraint file_github_url
        unique (file_github_url)
);
