from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from .models import User
from django.contrib.auth import login, logout, authenticate
from .forms import CustomUserCreationForm, CustomLoginForm

@login_required
def profile(request, username):
    user = get_object_or_404(User, username=username)
    profile = get_object_or_404(User, username=username)
    return render(request, 'profile.html', {'user': user, 'profile': profile})

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('user_accounts:profile', username=user.username)
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})


def accounts_index(request):
    return render(request, 'accounts_index.html')

def custom_logout(request):
    
    logout(request)
    return redirect('/')

def custom_login(request):
    form_class = CustomLoginForm
    template_name = 'registration/login.html'