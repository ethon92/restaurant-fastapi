from fastapi import APIRouter, Path, HTTPException
from web_app.models.feature import FavoriteRestaurant
from web_app.models.feature import RestaurantComment
from web_app.models.feature import UpdateFavorite
from web_app.mysql_connection import get_db_cursor
import pymysql
from typing import Annotated


router = APIRouter()


# 建立table函式
def create_table(cursor):
    create_query = """
        create table favorite(
            fav_id int primary key auto_increment,
            user_id int not null,
            restaurant_id varchar(50) not null,
            fav_note varchar(300)
        )
        """
    cursor.execute("show tables like %s", ("favorite"))
    result = cursor.fetchone()

    # 當沒有table時才建立
    if result is None:
        try:
            cursor.execute(create_query)
            print("favorite table is created!!")
        except pymysql.Error as e:
            print(f"Error create favorite table: {e}")


# 建立comment的table
def create_comments_table(cursor):
    create_query = """
    create table comments(
        comment_id int primary key auto_increment,
        user_id int not null,
        restaurant_id varchar(50) not null,             
        comment_content varchar(255) not null,   
        rating int not null check(rating >= 1 AND rating <= 5),
        comment_time DATETIME DEFAULT CURRENT_TIMESTAMP               
    )
    """
    cursor.execute("show tables like %s", ("comments"))
    result = cursor.fetchone()
    # 當沒有table時才建立
    if result is None:
        try:
            cursor.execute(create_query)
            print("comments table is created!!")
        except pymysql.Error as e:
            print(f"Error create comment table: {e}")


# 新增收藏餐廳路由
@router.post("/favorite")
def add_favorite(favorite: FavoriteRestaurant):
    try:
        # 在favorite中放入資料
        # 注意:提交資料要commit記得設為True
        with get_db_cursor(commit=True) as cursor:
            create_table(cursor)
            # 檢查此筆資料是否存在
            cursor.execute(
                "select * from favorite where user_id=%s and restaurant_id=%s",
                (favorite.user_id, favorite.restaurant_id),
            )
            result = cursor.fetchone()
            # 若已加入丟出409錯誤
            if result is not None:
                raise HTTPException(status_code=409, detail="已加入收藏餐廳中!!")

            sql = "insert into favorite(user_id, restaurant_id, fav_note) values(%s, %s, %s)"
            cursor.execute(
                sql, (favorite.user_id, favorite.restaurant_id, favorite.fav_note)
            )
            return {"status": "Success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"資料庫錯誤: {e}")


# 查詢收藏餐廳路由
@router.get("/favorite/{user_id}")
# 設定user_id必須大於0
def get_favorite(user_id: Annotated[int, Path(title="The ID of user", gt=0)]):
    try:
        with get_db_cursor() as cursor:
            sql = """
                select fav_id, user_id, fav_note, Name, CoverImage 
                from favorite join restaurants on restaurant_id = ID 
                where user_id =%s
            """
            cursor.execute(sql, (user_id))
            results = cursor.fetchall()
        return {"status": "Success", "user_id": user_id, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"資料庫錯誤: {e}")


# 刪除收藏餐廳路由
@router.delete("/favorite/{fav_id}")
def delete_favorite(
    fav_id: Annotated[int, Path(title="The ID of user", gt=0)]):
    try:
        with get_db_cursor(commit=True) as cursor:
            # 檢查此筆資料是否存在
            cursor.execute(
                "select * from favorite where fav_id=%s",
                (fav_id),
            )
            result = cursor.fetchone()
            # 若不存在丟出404錯誤
            if not result:
                raise HTTPException(status_code=404, detail="沒有此筆資料!!")
            delete_sql = "delete from favorite where fav_id=%s"
            cursor.execute(delete_sql, (fav_id))
            return {
                "status": "Success",
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"資料庫錯誤: {e}")


# 更新收藏餐廳路由
@router.put("/favorite")
def update_favorite(update: UpdateFavorite):
    try:
        with get_db_cursor(commit=True) as cursor:
            # 檢查此筆資料是否存在
            cursor.execute(
                "select * from favorite where fav_id=%s",
                (update.fav_id),
            )
            result = cursor.fetchone()
            # 若不存在丟出404錯誤
            if not result:
                raise HTTPException(status_code=404, detail="沒有此筆資料!!")
            update_sql = (
                "update favorite set fav_note=%s where fav_id=%s"
            )
            cursor.execute(
                update_sql, (update.fav_note, update.fav_id)
            )
            return {
                "status": "Success",
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"資料庫錯誤: {e}")


# 新增評論餐廳路由
@router.post("/comments")
def add_comment(comments: RestaurantComment):
    try:
        with get_db_cursor(commit=True) as cursor:
            create_table(cursor)
            cursor.execute(
                "select * from comments where user_id=%s and restaurant_id=%s",
                (
                    comments.user_id,
                    comments.restaurant_id,
                ),
            )
            result = cursor.fetchone()
            if result is not None:
                raise HTTPException(status_code=409, detail="已完成評論!!")

            sql = "insert into comments(user_id,restaurant_id, comment_content,rating) values(%s,%s,%s,%s)"
            cursor.execute(
                sql,
                (
                    comments.user_id,
                    comments.restaurant_id,
                    comments.comment_content,
                    comments.rating,
                ),
            )
            return {"status": "Success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"資料庫錯誤:{e}")


# 刪除評論餐廳路由
@router.delete("/comments/{user_id}/{restaurant_id}")
def delete_comment(
    user_id: Annotated[int, Path(tittle="The ID of user", gt=0)], restaurant_id: str
):
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(
                "select * from comments where user_id=%s and restaurant_id=%s",
                (user_id, restaurant_id),
            )
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="沒有此筆資料!!")
            delete_sql = "delete from comments where user_id=%s and restaurant_id=%s"
            cursor.execute(delete_sql, (user_id, restaurant_id))
            return {"status": "Success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"資料庫錯誤:{e}")


# 更新評論餐廳路由
@router.put("/comments")
def update_comment(update: RestaurantComment):
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(
                "select * from comments where user_id=%s and restaurant_id=%s",
                (update.user_id, update.restaurant_id),
            )
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="沒有此筆資料!!")
            update_sql = "update comments set comment_content=%s where user_id=%s and restaurant_id=%s"
            cursor.execute(
                update_sql,
                (update.comment_content, update.user_id, update.restaurant_id),
            )
            return {
                "status": "Success",
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"資料庫錯誤：{e}")
