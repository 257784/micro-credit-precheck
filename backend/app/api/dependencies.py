"""应用实例的依赖装配；测试可替换服务，不修改路由逻辑。"""
from app.repositories.sql_business import ApplicationRepository, ReviewRepository
from app.services.reviews import ReviewService

repository = ApplicationRepository()
reviews = ReviewService(repository, ReviewRepository())
