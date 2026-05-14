from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny,IsAuthenticated
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth import authenticate
from .serializers import RegisterSerializer,LoginSerializer,UserProfileSerializer,ChangePasswordSerializer
from drf_spectacular.utils import extend_schema



def get_tokens_for_user(user):
    """JWT tokens generate karta hai — login aur register dono mein use hoga."""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access' : str(refresh.access_token),
    }



class RegisterView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user   = serializer.save()
        tokens = get_tokens_for_user(user)

        return Response({
            'user'  : {'id': user.id, 'email': user.email, 'username': user.username},
            'tokens': tokens,
        }, status=status.HTTP_201_CREATED)
    



class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(
            request  = request,
            username = serializer.validated_data['email'],
            password = serializer.validated_data['password'],
        )

        if not user:
            return Response(
                {'error': 'Invalid email or password.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        tokens = get_tokens_for_user(user)

        return Response({
            'user'  : {'id': user.id, 'email': user.email, 'username': user.username},
            'tokens': tokens,
        }, status=status.HTTP_200_OK)
    


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = UserProfileSerializer(
            request.user,
            data    = request.data,
            partial = True,        # only update fields that are sent
            context = {'request': request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    

@extend_schema(
    summary="Change User Password",
    description="Allows authenticated users to change password",
    request=ChangePasswordSerializer,
    responses={
        200: {"type": "object", "properties": {
            "message": {"type": "string"}
        }}
    },
    tags=["Authentication"]
)
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data    = request.data,
            context = {'request': request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()

        # Blacklist current refresh token so user must login again
        refresh_token = request.data.get('refresh')
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except TokenError:
                pass  # already invalid, ignore

        return Response(
            {'message': 'Password changed successfully. Please login again.'},
            status=status.HTTP_200_OK
        )