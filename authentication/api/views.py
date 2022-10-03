from django.contrib.auth import get_user_model
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework import generics, viewsets, permissions, renderers
from authentication.api.renderers import JSONRenderer
from rest_framework_simplejwt.views import TokenObtainPairView
from authentication.api.serializers import LogInSerializer, UserSerializer


@permission_classes([IsAdminUser])
class SignUpView(generics.CreateAPIView):
    queryset = get_user_model().objects.all()
    serializer_class = UserSerializer


class LogInView(TokenObtainPairView):
    serializer_class = LogInSerializer


@permission_classes([IsAdminUser])
class UsersView(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    renderers = JSONRenderer
    queryset = get_user_model().objects.all()
    serializer_class = UserSerializer
