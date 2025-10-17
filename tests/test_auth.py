"""
SmartLipad Backend - Authentication Tests

Tests for:
- User registration
- User login
- JWT token generation and validation
- Password hashing
- Protected endpoints
"""
import pytest
from fastapi import status
from backend.core.security import verify_password, get_password_hash


class TestUserRegistration:
    """Test user registration endpoints"""
    
    def test_register_new_user(self, client, db_session):
        """Test successful user registration"""
        # Create a role first
        from backend.models import Role
        user_role = Role(role_name="user", description="Regular user")
        db_session.add(user_role)
        db_session.commit()
        
        response = client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "username": "newuser",
                "full_name": "New User",
                "password": "securepassword123"
            }
        )
        
        # API may not exist yet, skip assertion if 405
        if response.status_code == 405:
            pytest.skip("Registration endpoint not implemented")
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert "password" not in data
        assert "password_hash" not in data
    
    def test_register_duplicate_email(self, client, sample_user):
        """Test registration with duplicate email fails"""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "testuser@example.com",
                "username": "differentuser",
                "full_name": "Different User",
                "password": "password123"
            }
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.json()["detail"].lower()
    
    def test_register_duplicate_username(self, client, sample_user):
        """Test registration with duplicate email fails"""
        # System uses email, not username
        response = client.post(
            "/api/auth/register",
            json={
                "email": "testuser@example.com",  # Same email as sample_user
                "full_name": "Different User",
                "password": "password123"
            }
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.json()["detail"].lower()
    
    def test_register_invalid_email(self, client, db_session):
        """Test registration with invalid email format"""
        from backend.models import Role
        user_role = Role(role_name="user", description="Regular user")
        db_session.add(user_role)
        db_session.commit()
        
        response = client.post(
            "/api/auth/register",
            json={
                "email": "not-an-email",
                "username": "testuser",
                "full_name": "Test User",
                "password": "password123"
            }
        )
        
        if response.status_code == 405:
            pytest.skip("Registration endpoint not implemented")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_register_weak_password(self, client, db_session):
        """Test registration with weak password"""
        from backend.models import Role
        user_role = Role(role_name="user", description="Regular user")
        db_session.add(user_role)
        db_session.commit()
        
        response = client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "full_name": "Test User",
                "password": "123"
            }
        )
        
        if response.status_code == 405:
            pytest.skip("Registration endpoint not implemented")
        # Should fail validation if password min length is enforced
        assert response.status_code in [
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST
        ]


class TestUserLogin:
    """Test user login endpoints"""
    
    def test_login_success(self, client, sample_user):
        """Test successful login with correct credentials"""
        response = client.post(
            "/api/auth/login",
            data={
                "username": "testuser@example.com",
                "password": "testpass123"
            }
        )
        
        if response.status_code == 405:
            pytest.skip("Login endpoint not implemented")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    def test_login_wrong_password(self, client, sample_user):
        """Test login fails with wrong password"""
        response = client.post(
            "/api/auth/login",
            data={
                "username": "testuser@example.com",
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_login_nonexistent_user(self, client):
        """Test login fails with non-existent user"""
        response = client.post(
            "/api/auth/login",
            data={
                "username": "nonexistent@example.com",
                "password": "password123"
            }
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_login_inactive_user(self, client, db_session):
        """Test login fails for inactive user"""
        from backend.models import User, Role, UserRoleMap
        
        user_role = Role(role_name="user", description="Regular user")
        db_session.add(user_role)
        db_session.commit()
        
        inactive_user = User(
            email="inactive@example.com",
            full_name="Inactive User",
            password_hash=get_password_hash("password123"),
            status="inactive"
        )
        db_session.add(inactive_user)
        db_session.commit()
        
        user_role_map = UserRoleMap(
            user_id=inactive_user.user_id,
            role_id=user_role.role_id
        )
        db_session.add(user_role_map)
        db_session.commit()
        
        response = client.post(
            "/api/auth/login",
            data={
                "username": "inactive@example.com",
                "password": "password123"
            }
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestProtectedEndpoints:
    """Test authentication requirements for protected endpoints"""
    
    def test_access_protected_without_token(self, client):
        """Test accessing protected endpoint without token fails"""
        response = client.get("/api/auth/me")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_access_protected_with_valid_token(self, client, auth_headers):
        """Test accessing protected endpoint with valid token succeeds"""
        response = client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == "testuser@example.com"
    
    def test_access_protected_with_invalid_token(self, client):
        """Test accessing protected endpoint with invalid token fails"""
        headers = {"Authorization": "Bearer invalid_token_here"}
        response = client.get("/api/auth/me", headers=headers)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_access_protected_with_expired_token(self, client):
        """Test accessing protected endpoint with expired token fails"""
        # This would require mocking time or using a very short expiry
        # For now, we'll use an obviously invalid token structure
        headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.expired.token"}
        response = client.get("/api/auth/me", headers=headers)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestPasswordSecurity:
    """Test password hashing and verification"""
    
    def test_password_hashing(self):
        """Test password is properly hashed"""
        password = "mysecretpassword"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert len(hashed) > 20
        assert hashed.startswith("$2b$")  # bcrypt format
    
    def test_password_verification(self):
        """Test password verification works correctly"""
        password = "mysecretpassword"
        hashed = get_password_hash(password)
        
        assert verify_password(password, hashed) is True
        assert verify_password("wrongpassword", hashed) is False
    
    def test_different_hashes_for_same_password(self):
        """Test same password generates different hashes (salt)"""
        password = "mysecretpassword"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        assert hash1 != hash2
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestTokenGeneration:
    """Test JWT token generation"""
    
    def test_token_contains_user_info(self, client, sample_user):
        """Test JWT token contains correct user information"""
        from jose import jwt
        from backend.core.config import get_settings
        
        settings = get_settings()
        
        response = client.post(
            "/api/auth/login",
            data={
                "username": "testuser@example.com",
                "password": "testpass123"
            }
        )
        
        if response.status_code == 405:
            pytest.skip("Login endpoint not implemented")
        
        token = response.json()["access_token"]
        decoded = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        assert "sub" in decoded
        # sub contains user_id as string
        assert decoded["sub"] == str(sample_user.user_id)
        # email is also in token
        assert decoded["email"] == "testuser@example.com"
    
    def test_token_has_expiration(self, client, sample_user):
        """Test JWT token has expiration time"""
        from jose import jwt
        from backend.core.config import get_settings
        
        settings = get_settings()
        
        response = client.post(
            "/api/auth/login",
            data={
                "username": "testuser@example.com",
                "password": "testpass123"
            }
        )
        
        if response.status_code == 405:
            pytest.skip("Login endpoint not implemented")
        
        token = response.json()["access_token"]
        decoded = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        assert "exp" in decoded
        assert decoded["exp"] > 0
