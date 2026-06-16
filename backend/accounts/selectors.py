from .models import User


def get_user_by_username(username: str) -> User | None:
    return User.objects.filter(username=username).first()


def user_exists(username: str) -> bool:
    return User.objects.filter(username=username).exists()


def get_all_users_by_role(role: str):
    return User.objects.filter(role=role)


def get_doctors() -> list:
    return list(
        User.objects.filter(role__in=['doctor', 'hod'])
        .values('id', 'username', 'first_name', 'last_name', 'department', 'role')
        [:500]
    )


def get_hod_by_department(department: str) -> User | None:
    return User.objects.filter(role='hod', department=department).first()
