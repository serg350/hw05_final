from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, Client

from ..models import Post, Group

from http import HTTPStatus

User = get_user_model()


class URLTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='testuser')
        cls.group = Group.objects.create(
            title='Новая группа для тестов',
            slug='test-group',
            description='Тестовое описание'
        )
        cls.post = Post.objects.create(
            text='Новый текст представленный для примера',
            author=cls.user,
            group=cls.group
        )

    def setUp(self):
        self.guest_client = Client()
        self.user = User.objects.create_user(username='HasNoName')
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        self.post_author = Client()
        self.post_author.force_login(self.post.author)

    def test_urls_for_all_users(self):
        """Проверка на доступность страниц не авторизованным пользователям"""
        template_url = [
            '/',
            f'/group/{self.post.group.slug}/',
            f'/posts/{self.post.id}/',
            f'/profile/{self.post.author}/',
        ]
        for url in template_url:
            with self.subTest(url=url):
                responce = self.guest_client.get(url)
                self.assertEqual(responce.status_code, HTTPStatus.OK)

    def test_urls_for_authorisoried_users(self):
        """Проверка на возможность создания поста
         авторизованнму пользователю"""
        responce = self.authorized_client.get('/create/')
        self.assertEqual(responce.status_code, HTTPStatus.OK)

    def test_urls_for_no_authorisoried_users(self):
        """Проверка на возможность создания поста
         не авторизованнму пользователю"""
        responce_no_authoried = self.guest_client.get('/create/')
        self.assertEqual(
            responce_no_authoried.status_code, HTTPStatus.FOUND
        )

    def test_urls_for_edit_post_author_posts(self):
        """Проверка на возможность редактирования поста автору"""
        responce = self.post_author.get(
            f'/posts/{self.post.id}/edit/'
        )
        self.assertEqual(responce.status_code, HTTPStatus.OK)

    def test_urls_for_edit_post_no_author_posts(self):
        """Проверка на возможность редактирования
         поста просто авторизованному пользователю"""
        responce_no_author = self.authorized_client.get(
            f'/posts/{self.post.id}/edit/'
        )
        self.assertEqual(
            responce_no_author.status_code, HTTPStatus.FOUND
        )

    def test_urls_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        cache.clear()
        template_url_names = {
            '/': 'posts/index.html',
            f'/group/{self.post.group.slug}/': 'posts/group_list.html',
            '/create/': 'posts/create_post.html',
            f'/posts/{self.post.id}/': 'posts/post_detail.html',
            f'/profile/{self.post.author}/': 'posts/profile.html',
            f'/posts/{self.post.id}/edit/': 'posts/create_post.html',
        }
        for url, template in template_url_names.items():
            with self.subTest(url=url):
                responce = self.post_author.get(url)
                self.assertTemplateUsed(responce, template)

    def test_on_code_404(self):
        """Сервер возвращает код 404 и вызывает кастомный шаблон,
         если страница не найдена."""
        response = self.authorized_client.get('/123')
        self.assertTemplateUsed(response, 'core/404.html')
