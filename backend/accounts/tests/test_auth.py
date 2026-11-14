import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIClient, APIRequestFactory

from accounts.models import Profile
from accounts.permissions import IsAgent, IsRequester

User = get_user_model()
PASSWORD = "clave-de-prueba-123"


def make_user(username, role=None, **extra):
    user = User.objects.create_user(username, password=PASSWORD, **extra)
    if role:
        Profile.objects.create(user=user, role=role)
    return user


def login(client, username):
    response = client.post("/api/v1/auth/token/", {"username": username, "password": PASSWORD})
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
def test_login_devuelve_access_y_refresh(client):
    make_user("ana", "agent")

    assert set(login(client, "ana")) == {"access", "refresh"}


@pytest.mark.django_db
def test_login_con_clave_incorrecta_devuelve_401(client):
    make_user("ana", "agent")

    response = client.post("/api/v1/auth/token/", {"username": "ana", "password": "mala"})

    assert response.status_code == 401
    assert "access" not in response.json()


@pytest.mark.django_db
def test_login_de_usuario_inactivo_devuelve_401(client):
    make_user("ana", "agent", is_active=False)

    response = client.post("/api/v1/auth/token/", {"username": "ana", "password": PASSWORD})

    assert response.status_code == 401


@pytest.mark.django_db
def test_refresh_devuelve_un_access_valido(client):
    make_user("ana", "agent")
    tokens = login(client, "ana")

    response = client.post("/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]})

    assert response.status_code == 200
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['access']}")
    assert client.get("/api/v1/me/").status_code == 200


@pytest.mark.django_db
def test_refresh_no_acepta_un_access_token(client):
    make_user("ana", "agent")
    tokens = login(client, "ana")

    response = client.post("/api/v1/auth/token/refresh/", {"refresh": tokens["access"]})

    assert response.status_code == 401


@pytest.mark.django_db
def test_refresh_token_no_sirve_como_access(client):
    make_user("ana", "agent")
    tokens = login(client, "ana")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['refresh']}")

    assert client.get("/api/v1/me/").status_code == 401


@pytest.mark.django_db
def test_me_sin_token_devuelve_401(client):
    assert client.get("/api/v1/me/").status_code == 401


@pytest.mark.django_db
def test_me_con_token_invalido_devuelve_401(client):
    client.credentials(HTTP_AUTHORIZATION="Bearer no-es-un-token")

    assert client.get("/api/v1/me/").status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["agent", "requester"])
def test_me_devuelve_usuario_y_rol_como_codigo(client, role):
    make_user("ana", role, first_name="Ana", last_name="Gil")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login(client, 'ana')['access']}")

    response = client.get("/api/v1/me/")

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "ana"
    assert body["first_name"] == "Ana"
    assert body["role"] == role
    assert "password" not in body


@pytest.mark.django_db
def test_me_de_usuario_sin_perfil_devuelve_rol_nulo(client):
    make_user("sin.perfil")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login(client, 'sin.perfil')['access']}")

    response = client.get("/api/v1/me/")

    assert response.status_code == 200
    assert response.json()["role"] is None


@pytest.mark.django_db
def test_health_sigue_siendo_publico(client):
    assert client.get("/api/v1/health/").status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("permission", "role", "expected"),
    [
        (IsAgent, "agent", True),
        (IsAgent, "requester", False),
        (IsAgent, None, False),
        (IsRequester, "requester", True),
        (IsRequester, "agent", False),
        (IsRequester, None, False),
    ],
)
def test_permisos_por_rol(permission, role, expected):
    request = APIRequestFactory().get("/")
    request.user = make_user("u", role)

    assert permission().has_permission(request, None) is expected


@pytest.mark.parametrize("permission", [IsAgent, IsRequester])
def test_permisos_por_rol_rechazan_anonimos(permission):
    request = APIRequestFactory().get("/")
    request.user = AnonymousUser()

    assert permission().has_permission(request, None) is False


@pytest.mark.django_db
def test_cors_permite_el_origen_del_frontend_y_rechaza_otros(client):
    allowed = client.get("/api/v1/health/", HTTP_ORIGIN="http://localhost:5173")
    other = client.get("/api/v1/health/", HTTP_ORIGIN="http://malo.example")

    assert allowed["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert "Access-Control-Allow-Origin" not in other
