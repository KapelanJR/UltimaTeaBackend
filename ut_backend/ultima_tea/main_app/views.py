from django.db.models import query
from django.db.models.query import QuerySet
from django.http import request
from rest_framework.views import APIView
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework import generics, mixins, pagination
from authorization.models import Machine, CustomUser
from rest_framework import viewsets
from rest_framework.exceptions import APIException, ValidationError
from django.db.models import Q
from .models import *
from .tasks import *
from .serializers import *
from rest_framework.decorators import action

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

MAX_RECIPES_PER_USER = 50


def filter_recipes(params: dict, queryset: QuerySet):
    """
    List public recipes. List of query parameters
    name - name of recipe
    tea_type
    ingredient_1
    ingredient_2
    ingredient_3
    brewing_temperature_down
    brewing_temperature_up
    brewing_time_down
    brewing_time_up
    mixing_time_down
    mixing_time_up
    """
    for param in params:
        if param == "name":
            queryset = queryset.filter(recipe_name__iregex=f".*(?={params[param]}).*")
            continue
        if param == "tea_type":
            queryset = queryset.filter(tea_type__pk=params[param])
            continue
        if "ingredient" in param:
            queryset = queryset.filter(ingredients__ingredient__pk=params[param])
            continue
        if param == "brewing_temperature_down":
            queryset = queryset.filter(brewing_temperature__gte=params[param])
            continue
        if param == "brewing_temperature_up":
            queryset = queryset.filter(brewing_temperature__lte=params[param])
            continue
        if param == "brewing_time_down":
            queryset = queryset.filter(brewing_time__gte=params[param])
            continue
        if param == "brewing_time_up":
            queryset = queryset.filter(brewing_time__lte=params[param])
            continue
        if param == "mixing_time_down":
            queryset = queryset.filter(mixing_time__gte=params[param])
            continue
        if param == "mixing_time_up":
            queryset = queryset.filter(mixing_time__lte=params[param])
            continue
        if param == "min_score":
            queryset = queryset.filter(score__gte=params[param])
    return queryset


class WrongQuerystringValue(APIException):
    status_code = 422
    default_detail = "Invalid query string. Value must be numeric type."
    default_code = "wrong_query_string"


class NoMachineException(APIException):
    status_code = 404
    default_detail = "Your account has no machine. Contact administrator."
    default_code = "no_machine"


class IsOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_anonymous:
            return False
        try:
            obj.customuser_set.get(pk=request.user.id)
            return True
        except CustomUser.DoesNotExist:
            if request.user.is_superuser:
                return True
        except AttributeError:
            try:
                obj.machine.customuser_set.get(pk=request.user.id)
                return True
            except CustomUser.DoesNotExist:
                if request.user.is_superuser:
                    return True
            except AttributeError:
                if obj.recipe.author.id == request.user.id:
                    return True
                return False
            return False

    def has_permission(self, request, view):
        if request.user.is_anonymous:
            return False
        return True


class IsAuthorOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_anonymous:
            return False
        if obj.author == request.user:
            return True
        if request.user.is_superuser:
            return True
        return False

    def has_permission(self, request, view):
        if request.user.is_anonymous:
            return False
        return True


class MachineInfoViewSet(
    viewsets.GenericViewSet,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
):
    """
    List all user machines info
    Query params: all=bool - List all machines. Require admin permissions.
    """

    serializer_class = MachineInfoSerializer
    permission_classes = [IsOwnerOrAdmin]
    queryset = Machine.objects.all()
    permission_classes_by_action = {
        "list": [IsOwnerOrAdmin],
    }

    def list(self, request, *args, **kwargs):
        self.check_permissions(request)
        if self.request.query_params.get("all", False):
            obj = self.get_queryset()
        else:
            obj = self.get_queryset()
            if len(obj) == 0:
                raise NoMachineException()
            obj = obj[0]
            if obj.state_of_the_tea_making_process == 5:
                obj.state_of_the_tea_making_process = 0
                obj.save()
        result = super().list(request, *args, **kwargs)
        return result

    def create(self, request, *args, **kwargs):
        self.check_permissions(request)
        machine = MachineInfoSerializer(data=request.data)
        if machine.is_valid(raise_exception=True):
            machine.save()
        tea_container1 = TeasConatainerSerializer(
            data={
                "container_number": 1,
                "machine": request.data["machine_id"],
                "tea": None,
            }
        )
        tea_container2 = TeasConatainerSerializer(
            data={
                "container_number": 2,
                "machine": request.data["machine_id"],
                "tea": None,
            }
        )
        ing_container1 = IngredientsConatainerSerializer(
            data={
                "container_number": 3,
                "machine": request.data["machine_id"],
                "ingredient": None,
            }
        )
        ing_container2 = IngredientsConatainerSerializer(
            data={
                "container_number": 4,
                "machine": request.data["machine_id"],
                "ingredient": None,
            }
        )
        if (
            tea_container1.is_valid(raise_exception=True)
            and tea_container2.is_valid(raise_exception=True)
            and ing_container1.is_valid(raise_exception=True)
            and ing_container2.is_valid(raise_exception=True)
        ):
            tea_container1.save()
            tea_container2.save()
            ing_container1.save()
            ing_container2.save()
        return Response(machine.data)

    def get_permissions(self):
        try:
            # return permission_classes depending on `action`
            return [
                permission()
                for permission in self.permission_classes_by_action[self.action]
            ]
        except KeyError:
            # action is not set return default permission_classes
            return [permissions.IsAdminUser()]

    def get_queryset(self):
        if self.request.user.is_superuser:
            if self.request.query_params.get("all", False):
                return Machine.objects.all()
        return Machine.objects.filter(customuser=self.request.user)


class CheckTokenView(APIView):
    queryset = CustomUser.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, format=None):
        self.check_permissions(request)
        return Response(status=200)


class UpdateTeaContainersView(generics.UpdateAPIView):
    """
    List or edit tea containers
    """

    serializer_class = UpdateTeasConatainerSerializer
    permission_classes = [IsOwnerOrAdmin]
    queryset = MachineContainers.objects.all()

    def update(self, request, pk, *args, **kwargs):
        data = super().update(request, pk, *args, **kwargs)
        machine = request.user.machine
        containers = MachineContainers.objects.filter(
            machine__customuser=self.request.user
        )
        ingredients = containers.filter(container_number__gte=3)
        teas = containers.filter(container_number__lte=2)
        ingredients = IngredientsConatainerSerializer(ingredients, many=True)
        teas = TeasConatainerSerializer(teas, many=True)
        update_all_containers.delay(
            {
                "tea_containers": teas.data,
                "ingredient_containers": ingredients.data,
            },
            machine.machine_id,
        )
        return data

    def get_queryset(self):
        return MachineContainers.objects.filter(
            Q(machine__customuser=self.request.user) & (Q(container_number__lte=2))
        )


class UpdateIngredientContainersView(generics.UpdateAPIView):
    """
    List or edit ingredient containers
    """

    serializer_class = UpdateIngredientsConatainerSerializer
    permission_classes = [IsOwnerOrAdmin]
    queryset = MachineContainers.objects.all()

    def get_queryset(self):
        return MachineContainers.objects.filter(
            Q(machine__customuser=self.request.user) & (Q(container_number__gte=3))
        )

    def update(self, request, pk, *args, **kwargs):
        data = super().update(request, pk, *args, **kwargs)
        machine = request.user.machine
        containers = MachineContainers.objects.filter(
            machine__customuser=self.request.user
        )
        ingredients = containers.filter(container_number__gte=3)
        teas = containers.filter(container_number__lte=2)
        ingredients = IngredientsConatainerSerializer(ingredients, many=True)
        teas = TeasConatainerSerializer(teas, many=True)
        update_all_containers.delay(
            {
                "tea_containers": teas.data,
                "ingredient_containers": ingredients.data,
            },
            machine.machine_id,
        )
        return data


class GetMachineContainers(generics.ListAPIView):

    queryset = MachineContainers.objects.all()
    permission_classes = [IsOwnerOrAdmin]
    serializer_class = IngredientsConatainerSerializer

    def get_queryset(self):
        return MachineContainers.objects.filter(machine__customuser=self.request.user)

    def list(self, request, *args, **kwargs):
        self.check_permissions(request)
        queryset = self.get_queryset()
        ingredients = queryset.filter(container_number__gte=3)
        teas = queryset.filter(container_number__lte=2)
        ingredients = IngredientsConatainerSerializer(ingredients, many=True)
        teas = TeasConatainerSerializer(teas, many=True)
        return Response(
            {"tea_containers": teas.data, "ingredient_containers": ingredients.data}
        )


class ListPublicRecipes(generics.ListAPIView):
    """
    List public recipes with filters
    """

    class RecipesSetPagination(pagination.PageNumberPagination):
        page_size = 6
        page_size_query_param = "size"
        max_page_size = 6

    # serializer_class = RecipesSerializer2
    serializer_class = RecipesSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Recipes.objects.filter(is_public=True)
    pagination_class = RecipesSetPagination

    def get_queryset(self):
        try:
            return filter_recipes(
                self.request.query_params,
                Recipes.objects.filter(Q(is_public=True)),
            )
        except ValueError:
            raise WrongQuerystringValue()

    def list(self, request, *args, **kwargs):
        self.check_permissions(request)
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = RecipesSerializer(
                page, many=True, context={"user": request.user}
            )
            return self.get_paginated_response(serializer.data)
        serializer = RecipesSerializer(page, many=True, context={"user": request.user})
        return Response(serializer.data)


class UserRecipesViewSet(viewsets.ModelViewSet):
    """
    Used to do all staff with logged user recipes. Doesnt have access to other recipes.
    Use PATCH to update existing ingredients in recipes
    Use PUT to create new recipe or pass id to edit existing
    """

    permission_classes_by_action = {
        "update": [IsAuthorOrAdmin],
        "partial_update": [IsAuthorOrAdmin],
        "destroy": [IsAuthorOrAdmin],
        "create": [permissions.IsAuthenticated],
        "list": [permissions.IsAuthenticated],
        "retrieve": [IsAuthorOrAdmin],
    }
    queryset = Recipes.objects.all()

    # serializer_class = RecipesSerializer2
    serializer_class = RecipesSerializer

    def get_permissions(self):
        try:
            # return permission_classes depending on `action`
            return [
                permission()
                for permission in self.permission_classes_by_action[self.action]
            ]
        except KeyError:
            # action is not set return default permission_classes
            return [permissions.IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        if Recipes.objects.filter(author=request.user).count() > MAX_RECIPES_PER_USER:
            raise ValidationError(
                {
                    "detail": f"You have reached maxium numer of recipes ({MAX_RECIPES_PER_USER}). In order to create new recipe delete old ones."
                }
            )
        return super().create(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        self.check_permissions(request)
        queryset = Recipes.objects.filter(author=request.user)
        serializer = self.serializer_class(queryset, many=True)
        return Response(serializer.data)

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH", "POST"]:
            return WriteRecipesSerializer
        return super().get_serializer_class()

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=["post", "put"])
    def vote(self, request, pk):
        if request.method == "PUT":
            # Modify score
            try:
                obj = VotedRecipes.objects.get(
                    Q(user_id=request.user.pk) & Q(recipe_id=pk)
                )
                prev_score = obj.score
                serializer = RecipeVoteSerializer(
                    instance=obj,
                    data=request.data | {"user": request.user.pk, "recipe": pk},
                )
                if serializer.is_valid(raise_exception=True):
                    obj = serializer.save()
                    recipe = Recipes.objects.get(pk=pk)
                    recipe.score = (
                        (recipe.score * recipe.votes) - prev_score + obj.score
                    ) / (recipe.votes)
                    recipe.save()
                    return Response({"score": recipe.score}, status=200)
            except VotedRecipes.DoesNotExist:
                pass
        serializer = RecipeVoteSerializer(
            data={"user": request.user.pk, "recipe": pk} | request.data
        )
        if serializer.is_valid(raise_exception=True):
            # Create new score
            obj = serializer.save()
            recipe = Recipes.objects.get(pk=pk)
            recipe.score = ((recipe.score * recipe.votes) + obj.score) / (
                recipe.votes + 1
            )
            recipe.votes += 1
            recipe.save()
        return Response({"score": recipe.score}, status=201)


class IngredientsViewSet(viewsets.ModelViewSet):
    serializer_class = IngredientSerializer
    queryset = Ingredients.objects.all()
    permission_classes_by_action = {
        "list": [permissions.IsAuthenticated],
    }

    def get_permissions(self):
        if self.action in self.permission_classes_by_action:
            return [
                permission()
                for permission in self.permission_classes_by_action[self.action]
            ]
        else:
            return [permissions.IsAdminUser()]

    def list(self, request, *args, **kwargs):
        self.check_permissions(request)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        self.check_permissions(request)
        return super().retrieve(request, *args, **kwargs)


class TeasViewSet(viewsets.ModelViewSet):
    serializer_class = TeaSerializer
    queryset = Teas.objects.all()
    permission_classes_by_action = {
        "list": [permissions.IsAuthenticated],
    }

    def get_permissions(self):
        if self.action in self.permission_classes_by_action:
            return [
                permission()
                for permission in self.permission_classes_by_action[self.action]
            ]
        else:
            return [permissions.IsAdminUser()]

    def list(self, request, *args, **kwargs):
        self.check_permissions(request)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        self.check_permissions(request)
        return super().retrieve(request, *args, **kwargs)


class DeleteRecipeIngredient(generics.DestroyAPIView):
    queryset = IngredientsRecipes.objects.all()
    permission_classes = [IsOwnerOrAdmin]
    serializer_class = IngredientsRecipesSerializer


class ListTeas(generics.ListAPIView):
    queryset = Teas.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TeaSerializer

    def list(self, request, *args, **kwargs):
        self.check_permissions(request)
        return super().list(request, *args, **kwargs)


class SendRecipeView(APIView):
    queryset = IngredientsRecipes.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = PrepareRecipeSerializer

    @swagger_auto_schema(
        operation_description="Sending recipe to machine",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["id"],
            properties={
                "id": openapi.Schema(type=openapi.TYPE_INTEGER),
                "tea_portion": openapi.Schema(type=openapi.TYPE_INTEGER),
            },
        ),
    )
    def post(self, request, format=None):
        self.check_permissions(request)
        try:
            recipe = PrepareRecipeSerializer(
                data=request.data,
                context={"tea_portion": request.data["tea_portion"]},
            )
        except:
            raise ValidationError({"detail": "Wrong data"})

        if recipe.is_valid(raise_exception=True):
            recipe = recipe.data
            print(recipe)
            validation_errors = []
            machine = Machine.objects.get(pk=request.user.machine.machine_id)
            if machine.machine_status == 0:
                validation_errors.append("Machine is not connected.")
            if not machine.is_mug_ready:
                validation_errors.append("Mug is not ready.")
            tea_containers = MachineContainers.objects.filter(
                Q(machine=machine) & Q(container_number__lte=2)
            )
            no_tea = True
            for tea_container in tea_containers:
                if tea_container.tea.id == recipe["tea_type"]["id"]:
                    if tea_container.ammount >= recipe["tea_herbs_ammount"]:
                        no_tea = False
                    else:
                        validation_errors.append("Not enough tea herbs in container.")
                    break
            if no_tea:
                validation_errors.append(
                    "Given tea type is not available in your tea containers."
                )

            ingredient_containers = MachineContainers.objects.filter(
                Q(machine=request.user.machine) & Q(container_number__gte=3)
            )

            ingredients = recipe["ingredients"]
            for ingredient in ingredients:
                for ingredient_container in ingredient_containers:
                    no_ingredient = True
                    if ingredient_container.ingredient == ingredient["ingredient"]:
                        if ingredient_container.ammount >= ingredient["ammount"]:
                            no_ingredient = False
                        else:
                            validation_errors.append(
                                "Not enough ingredient in container."
                            )
                        break
                if no_ingredient:
                    validation_errors.append(
                        f"Ingredient: {ingredient['ingredient']['ingredient_name']}, of required ammount: {ingredient['ammount']}, is not avaible in your machine."
                    )
            if not machine.water_container_weight >= (recipe["tea_portion"] + 60):
                validation_errors.append("Not enough water.")

            if len(validation_errors) > 0:
                raise ValidationError({"detail": validation_errors})

            send_recipe.delay(recipe, machine.machine_id)
            return Response({}, status=200)


class AddToFavouritesView(generics.UpdateAPIView):

    serializer_class = FavouritesSerializer
    queryset = Recipes.objects.all()
    permission_classes = [IsAuthorOrAdmin]

    def get_queryset(self):
        return Recipes.objects.filter(author=self.request.user)

    def update(self, request, pk, *args, **kwargs):
        data = super().update(request, *args, **kwargs)
        machine = request.user.machine
        recipes = Recipes.objects.filter(Q(author=request.user) & Q(is_favourite=True))
        recipes = PrepareRecipeSerializer(recipes, many=True)
        favourites_edit_offline.delay(recipes.data, machine.machine_id)
        return data
