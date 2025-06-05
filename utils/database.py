import os
import json
import mysql.connector as sql
import dotenv
from utils.enums import *

dotenv.load_dotenv()

sql_config = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("SQL_PORT", 3306),
    "user": os.getenv("SQL_USERNAME", "root"),
    "password": os.getenv("SQL_PASSWORD", "root"),
    "database": os.getenv("SQL_DATABASE", "proj"),
}

db = sql.connect(**sql_config)

def add_project(project_path, file_github_url, starcnt):
    c = db.cursor()
    c.execute(
        f"INSERT IGNORE INTO progress (project_name,file_github_url,stars_count) VALUES (%s,%s,%s)",
        (project_path, file_github_url, starcnt),
    )
    db.commit()
    c.close()
    return c.lastrowid


def fetch_project_at_step(stepid):
    c = db.cursor()
    c.execute(
        f"SELECT id,project_name,downloaded_file_name,file_github_url FROM progress WHERE step=%s"
        f" AND is_paused=0 ORDER BY stars_count DESC LIMIT 1;",
        (stepid,),
    )
    a = c.fetchone()
    db.commit()
    c.close()
    if not a:
        return None, None, None, None
    return a


def fetch_project_at_step_with_pause_reason(step_id, pause_reason):
    c = db.cursor()
    c.execute(
        f"SELECT id,project_name,downloaded_file_name,file_github_url FROM progress WHERE step=%s"
        f" and is_paused=1 and pause_reason=%s ORDER BY stars_count DESC LIMIT 1;",
        (step_id, pause_reason,),
    )
    a = c.fetchone()
    db.commit()
    c.close()
    if not a:
        return None, None, None, None
    return a


def change_project_step(project_id, step_val):
    c = db.cursor()
    c.execute(f"UPDATE progress SET step = %s, updated_at = now()  WHERE id = %s", (step_val, project_id))
    db.commit()
    c.close()


def pause_project(project_id, reason_val):
    c = db.cursor()
    c.execute(
        f"UPDATE progress SET is_paused = 1, pause_reason = %s, updated_at=now() WHERE id = %s",
        (reason_val, project_id),
    )
    db.commit()
    c.close()


def update_filename(project_id, downloaded_file_name):
    c = db.cursor()
    c.execute(
        f"UPDATE progress SET downloaded_file_name = %s WHERE id = %s",
        (downloaded_file_name, project_id),
    )
    db.commit()
    c.close()


def save_semgrep_output(project_id, out):
    c = db.cursor()
    c.execute(f"UPDATE progress SET semgrep_out = %s, updated_at=now() WHERE id = %s", (out, project_id))
    db.commit()
    c.close()


def add_timing_to_project(project_id, tname, tval):
    c = db.cursor()
    c.execute(
        f"SELECT stuff_times FROM progress WHERE id=%s LIMIT 1;", (project_id,)
    )
    r = c.fetchone()[0]
    if not r:
        r = {}
    else:
        r = json.loads(r)

    r[tname] = tval
    r = json.dumps(r)

    c.execute(f"UPDATE progress SET stuff_times = %s WHERE id = %s", (r, project_id))
    db.commit()
    c.close()


def set_vulnerable_to_dos(proj_id, dos_status_val):
    c = db.cursor()
    c.execute(
        f"UPDATE progress SET is_vulnerable_to_dos = %s, updated_at=now() WHERE id = %s",
        (dos_status_val, proj_id),
    )
    db.commit()
    c.close()


def set_is_local_flag_and_unpause(proj_id):
    c = db.cursor()
    c.execute(
        f"UPDATE progress SET is_local = 1, is_paused = 0, pause_reason=0, updated_at=now() WHERE id = %s",
        (proj_id,),
    )
    db.commit()
    c.close()


def fetch_project_at_step_with_dos_status(stepid, dos_status):
    c = db.cursor()
    c.execute(
        f"SELECT id,project_name,downloaded_file_name,file_github_url FROM progress WHERE step=%s"
        f" and is_paused=0 and is_vulnerable_to_dos=%s ORDER BY stars_count DESC LIMIT 1;",
        (stepid, dos_status,),
    )
    a = c.fetchone()
    db.commit()
    c.close()
    if not a:
        return None, None, None, None
    return a


def fetch_project_without_cvss():
    c = db.cursor()
    c.execute(
        "SELECT id,is_local,is_vulnerable_to_dos FROM progress WHERE step>=%s"
        " AND (vector_string IS NULL OR BASE_SCORE IS NULL OR severity IS NULL) LIMIT 1;",
        (STEP_POC_SUCCESS,),
    )
    row = c.fetchone()
    db.commit()
    c.close()
    return row


def update_cvss(proj_id, vector_string, base_score, severity):
    c = db.cursor()
    c.execute(
        f"UPDATE progress SET vector_string = %s, base_score = %s, severity = %s, step = %s, updated_at=now() WHERE id = %s",
        (vector_string, base_score, severity, STEP_POC_CVSS_READY, proj_id,),
    )
    db.commit()
    c.close()


def set_field(proj_id, col, val):
    c = db.cursor()
    c.execute(
        f"UPDATE progress SET {col} = %s, updated_at=now() WHERE id = %s",
        (val, proj_id),
    )
    db.commit()
    c.close()


def get_field(proj_id, col, default = None):
    c = db.cursor()
    c.execute(
        f"select {col} from progress WHERE id = %s",
        (proj_id,),
    )
    row = c.fetchone()[0]
    db.commit()
    c.close()
    if not row:
        row = default
    return row


def get_all(stepid):
    c = db.cursor(dictionary=True)
    c.execute(
        f"SELECT * FROM progress WHERE step=%s AND is_paused=0 ORDER BY stars_count DESC",
        (stepid,),
    )
    a = c.fetchall()
    db.commit()
    c.close()
    return a


def get_by_id(project_id):
    c = db.cursor(dictionary=True)
    c.execute(
        f"SELECT * FROM progress WHERE id=%s AND is_paused=0 limit 1",
        (project_id,),
    )
    row = c.fetchone()
    db.commit()
    c.close()
    return row

def get_patchready_projects(id):
    c = db.cursor(dictionary=True)
    c.execute(
        #f"SELECT * FROM progress WHERE step=%s AND project_name not like '%ctf%' AND project_name not like '%hue%' AND is_paused=0 AND project_name not like 'GlobalCarbonAtlas%' AND id<8000 AND pull_request_link is NULL AND id=360 ORDER BY stars_count ASC",
        #f"-- SELECT * FROM progress WHERE step=%s AND stars_count >= 4 and stars_count <= 100 AND project_name not like '%ctf%' AND project_name not like '%hue%' AND is_paused=0 AND project_name not like 'GlobalCarbonAtlas%' AND pull_request_link is NULL ORDER BY stars_count DESC",
        f"SELECT * FROM progress WHERE step=%s AND id={id} AND stars_count >= 100  AND project_name not like '%ctf%' AND project_name not like '%hue%' AND is_paused=0 AND project_name not like 'GlobalCarbonAtlas%' AND pull_request_link is NULL ORDER BY stars_count DESC",
        (STEP_PATCH_READY,),
    )
    a = c.fetchall()
    c.close()
    return a

def get_maintained_status_missing_projects():
    c = db.cursor(dictionary=True)
    c.execute(
        f"SELECT * FROM progress WHERE step>=6 AND is_maintained is NULL ORDER BY stars_count DESC",
    )
    a = c.fetchall()
    c.close()
    return a

def get_firstappeard_projects():
    c = db.cursor(dictionary=True)
    c.execute(
        f"SELECT * FROM progress WHERE step>=6 AND first_appeared_at is NULL ORDER BY stars_count DESC ",
    )
    a = c.fetchall()
    c.close()
    return a


def set_pull_request(proj_id,pull_request_link):
    c = db.cursor()
    c.execute(
        f"UPDATE progress SET pull_request_link=%s, step=%s, updated_at = now() WHERE id=%s",
        (pull_request_link,STEP_PATCH_SENT,proj_id),
    )
    db.commit()
    c.close()
