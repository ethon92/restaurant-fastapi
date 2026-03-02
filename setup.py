from web_app.mysql_connection import get_db_cursor
import pymysql
from fastapi import HTTPException


class setup_database:
    def __init__(self, name, sql, cursor):
        self.name = name
        self.sql = sql
        self.cursor = cursor

    def create_table(self):
        cursor.execute("show tables like %s", (f"{self.name}"))
        result = cursor.fetchone()

        # 當沒有table時才建立
        if result is None:
            try:
                cursor.execute(self.sql)
                print(f"{self.name} table is created!!")
            except pymysql.Error as e:
                print(f"Error create {self.name} table: {e}")
        else:
            print(f"{self.name} table exits!!")


create_comments = """create table comments(
        comment_id int primary key auto_increment,
        user_id int not null,
        restaurant_id varchar(50) not null,             
        comment_content varchar(255) not null,   
        rating int not null check(rating >= 1 AND rating <= 5),
        comment_time DATETIME DEFAULT CURRENT_TIMESTAMP               
    )"""

create_favorite = """
        create table favorite(
            fav_id int primary key auto_increment,
            user_id int not null,
            restaurant_id varchar(50) not null,
            fav_note varchar(300),
            foreign key (user_id) references users(user_id),
            foreign key (restaurant_id) references restaurants(id)
        )
        """

create_users = """
        CREATE TABLE `users` (
                `user_id` INTEGER NOT NULL AUTO_INCREMENT,
                `user_name` VARCHAR(20),
                `user_email` VARCHAR(30) NOT NULL,
                `user_password` VARCHAR(255) NOT NULL,
                `user_birthday` DATE NOT NULL,
                `user_role` BOOLEAN DEFAULT 0,
                `avatar_path` VARCHAR(255) NULL,
                PRIMARY KEY (`user_id`),
                UNIQUE KEY `uq_users_email` (`user_email`)
        );
"""

create_reservations = """
CREATE TABLE reservations (
    booking_id INT AUTO_INCREMENT PRIMARY KEY,
    restaurant_name VARCHAR(100),
    user_id INT,
    user_name VARCHAR(50),
    phone VARCHAR(20),
    email VARCHAR(100),
    party_size INT,
    note TEXT,
    booking_time DATETIME,
    booking_status VARCHAR(30) DEFAULT 'confirmed',
    is_commented TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已評論：0為否，1為是',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_reservations_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE RESTRICT,
    CONSTRAINT unique_booking UNIQUE (user_id, booking_time)
);
"""

try:
    with get_db_cursor(commit=True) as cursor:
        setup_database("comments", create_comments, cursor).create_table()
        setup_database("favorite", create_favorite, cursor).create_table()
        setup_database("users", create_users, cursor).create_table()
        setup_database("reservations", create_reservations, cursor).create_table()
except HTTPException:
    raise
except Exception as e:
    raise HTTPException(status_code=500, detail=f"資料庫錯誤: {e}")
