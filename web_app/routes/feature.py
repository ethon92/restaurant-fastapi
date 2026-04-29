from fastapi import APIRouter, Path, HTTPException
from web_app.models.feature import FavoriteRestaurant
from web_app.models.feature import RestaurantComment
from web_app.models.feature import UpdateFavorite
from web_app.models.feature import updateRestaurantComment
from web_app.mysql_connection import get_db_cursor
import pymysql
from typing import Annotated
from web_app.services.favorite_service import FavoriteService

router = APIRouter()
favorite_service = FavoriteService()


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
async def add_favorite_api(fav: FavoriteRestaurant):
    if favorite_service.add_favorite(fav):
        return {"status": "Success"}
    raise HTTPException(status_code=400, detail="新增失敗")


# 查詢收藏餐廳路由從使用者頁面
@router.get("/favorite/{user_id}")
async def get_my_favorites(user_id: int):
    results = favorite_service.get_favorite_list_with_detail(user_id)
    return {"status": "success", "user_id": user_id, "results": results}


# 取得收藏餐廳路由從餐廳頁面
@router.get("/favorite/{user_id}/{restaurant_id}")
async def get_favorite_restaurant(user_id: int, restaurant_id: str):
    try:
        exists = favorite_service.is_favorite(user_id, restaurant_id)

        return {"status": "Success", "results": exists}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"伺服器錯誤: {e}")


# 刪除收藏餐廳路由從使用者頁面
@router.delete("/favorite/{fav_id}")
async def remove_favorite(fav_id: int):
    if favorite_service.delete_by_id(fav_id):
        return {"status": "Success"}
    raise HTTPException(status_code=400, detail="刪除失敗")


# 取消收藏餐廳路由從餐廳頁面
@router.delete("/favorite/{user_id}/{restaurant_id}")
def delete_favorite_restaurant(user_id: int, restaurant_id: str):
    success = favorite_service.delete_by_user_and_restaurant(user_id, restaurant_id)

    if not success:
        # 如果失敗（可能是沒資料或資料庫錯誤），拋出錯誤
        raise HTTPException(status_code=404, detail="刪除失敗，可能無此收藏記錄")

    return {"status": "Success"}


# 更新收藏餐廳路由
@router.put("/favorite")
async def update_favorite_api(update_data: UpdateFavorite):
    if favorite_service.update_favorite_notes(update_data):
        return {"status": "Success"}
    raise HTTPException(status_code=400, detail="更新失敗")


# 新增評論餐廳路由
@router.post("/comments")
def add_comment(comments: RestaurantComment):
    try:
        with get_db_cursor(commit=True) as cursor:
            create_table(cursor)
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
            return {"status": "評論新增"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"資料庫錯誤:{e}")


# 刪除評論餐廳路由
@router.delete("/comments/{user_id}/{comment_id}")
def delete_comment(
    user_id: Annotated[int, Path(tittle="The ID of user", gt=0)], comment_id: int
):
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(
                "select * from comments where user_id=%s and comment_id=%s",
                (user_id, comment_id),
            )
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="沒有此筆資料!!")
            delete_sql = "delete from comments where user_id=%s and comment_id=%s"
            cursor.execute(delete_sql, (user_id, comment_id))
            return {"status": "Success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"資料庫錯誤:{e}")


# 更新評論餐廳路由
@router.put("/comments")
def update_comment(update: updateRestaurantComment):
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(
                "select * from comments where user_id=%s and comment_id=%s",
                (update.user_id, update.comment_id),
            )
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="沒有此筆資料!!")
            update_sql = "update comments set comment_content=%s where user_id=%s and comment_id=%s"
            cursor.execute(
                update_sql,
                (update.comment_content, update.user_id, update.comment_id),
            )
            return {
                "status": "Success",
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"資料庫錯誤：{e}")
