import requests
import unittest
from django.test import TestCase, client
import json
from django.test import Client
import rest_framework

from django.db.models import Q
from rest_framework.response import Response
from authorization.models import CustomUser
from .models import (
    Ingredients,
    IngredientsRecipes,
    Machine,
    MachineContainers,
    Recipes,
    Teas,
)


class TestCases(TestCase):
    class User:
        def __init__(self, email, password, machine) -> None:
            self.email = email
            self.password = password
            self.machine = machine
            self.user_id = 0
            self.token = ""

        def to_json(self):
            return {
                "email": self.email,
                "password": self.password,
                "machine": self.machine,
            }

    def create_objects(self):

        ing1 = Ingredients.objects.create(ingredient_name="Cukier", type=2)
        ing3 = Ingredients.objects.create(ingredient_name="Syrop malinowy", type=1)
        ing2 = Ingredients.objects.create(ingredient_name="Sok z cytryny", type=1)
        Ingredients.objects.create(ingredient_name="Miód", type=1)
        tea1 = Teas.objects.create(tea_name="Czarna herbata")
        tea2 = Teas.objects.create(tea_name="Zielona herbata")
        Teas.objects.create(tea_name="Biała herbata")
        MachineContainers.objects.create(
            machine=self.machine, container_number=1, tea=tea1
        )
        MachineContainers.objects.create(
            machine=self.machine, container_number=2, tea=tea2
        )
        MachineContainers.objects.create(
            machine=self.machine, container_number=3, ingredient=ing1
        )

        recipe = Recipes.objects.create(
            author=CustomUser.objects.get(pk=self.user.user_id),
            recipe_name="test",
            tea_type=tea1,
        )

        recipe_pub1 = Recipes.objects.create(
            author=CustomUser.objects.get(pk=self.user.user_id),
            recipe_name="test1",
            tea_type=tea2,
        )

        recipe_pub2 = Recipes.objects.create(
            author=CustomUser.objects.get(pk=self.user.user_id),
            recipe_name="test2",
            tea_type=tea1,
            is_public = True,
        )

        IngredientsRecipes.objects.create(recipe=recipe, ingredient=ing1, ammount=12.5)
        IngredientsRecipes.objects.create(recipe=recipe, ingredient=ing2, ammount=3.33)
        IngredientsRecipes.objects.create(recipe=recipe_pub1, ingredient=ing3, ammount=27.33)
        IngredientsRecipes.objects.create(recipe=recipe_pub2, ingredient=ing2, ammount=32.33)
        IngredientsRecipes.objects.create(recipe=recipe_pub2, ingredient=ing1, ammount=13.33)

    def setUp(self):
        self.client = Client()
        self.user = self.User("test@wp.pl", "Test1234", "123")
        self.machine = Machine.objects.create(machine_id="123")
        self.create_user(self.user)
        self.obtain_token(self.user)
        self.create_objects()
        self.client = Client(HTTP_AUTHORIZATION="Bearer {}".format(self.user.token))

    def create_user(self, user):
        """
        Create user in database
        """
        data = user.to_json()
        return self.client.post("/user/", data)

    def obtain_token(self, user):
        """
        Obtain a token, and save user id and this token in user instance
        """
        response = self.client.post("/token/", user.to_json())
        user.token = response.json()["access"]
        user.user_id = response.json()["user_id"]

    def test_register(self):
        data = self.client.get(f"/user/{self.user.user_id}/")
        self.assertEqual(data.status_code, 200)
        data = data.json()
        self.assertEqual(data["email"], self.user.email)
        self.assertEqual(data["machine"], self.user.machine)

    def test_user(self):
        """
        Change email of user
        """
        data = {"email": "nowy@wp.pl"}
        data = self.client.patch(
            f"/user/{self.user.user_id}/", data, content_type="application/json"
        )
        self.assertEqual(data.status_code, 200)
        data = data.json()
        self.assertEqual(data["email"], "nowy@wp.pl")
        """
        Change to orginal one
        """
        data = {"email": self.user.email}
        data = self.client.patch(
            f"/user/{self.user.user_id}/", data, content_type="application/json"
        )
        self.assertEqual(data.status_code, 200)
        data = data.json()
        self.assertEqual(data["email"], self.user.email)

        """
        Create user with same email
        """
        self.user2 = self.User("test@wp.pl", "Test1234", "123")
        response = self.create_user(self.user2)
        self.assertEqual(response.status_code, 400)

        """
        Create new user and try to access his data
        """
        self.user2.email = "test2@wp.pl"
        response = self.create_user(self.user2)
        self.assertEqual(response.status_code, 201)
        self.obtain_token(self.user2)
        data = self.client.get(f"/user/{self.user2.user_id}/")
        self.assertEqual(data.status_code, 403)

        """
        Change password
        """
        data = {"password": "test1234"}
        data = self.client.patch(
            f"/user/{self.user.user_id}/", data, content_type="application/json"
        )
        self.user.password = "test1234"
        self.obtain_token(self.user)
        self.client = Client(HTTP_AUTHORIZATION="Bearer {}".format(self.user.token))

        """
        Try to delete other user account
        """
        data = self.client.delete(f"/user/{self.user2.user_id}/")
        self.assertEqual(data.status_code, 403)

        self.client = Client(HTTP_AUTHORIZATION="Bearer {}".format(self.user2.token))
        """
        Delete your account
        """
        data = self.client.delete(f"/user/{self.user2.user_id}/")
        self.client = Client(HTTP_AUTHORIZATION="Bearer {}".format(self.user.token))
        self.assertEqual(data.status_code, 204)

    def test_get_machine_info(self):
        response = self.client.get("/machine/")
        self.assertEqual(response.status_code, 200)
        machine = [
            {
                "machine_id": "123",
                "brewing_temperature": 0.0,
                "air_temperature": 0.0,
                "mug_temperature": 0.0,
                "water_container_weight": 0.0,
                "is_mug_ready": False,
                "state_of_the_tea_making_process": 0,
                "machine_status": 0,
            }
        ]
        data = response.json()
        self.assertEqual(machine, data)

    def test_containers(self):
        """
        Modify and get machine containers info
        """
        machine_containers = {
            "tea_containers": [
                {
                    "id": 1,
                    "ammount": 0.0,
                    "tea": {"tea_name": "Czarna herbata", "id": 1},
                    "container_number": 1,
                },
                {
                    "id": 2,
                    "ammount": 0.0,
                    "tea": {"tea_name": "Zielona herbata", "id": 2},
                    "container_number": 2,
                },
            ],
            "ingredient_containers": [
                {
                    "id": 3,
                    "ammount": 0.0,
                    "ingredient": {
                        "ingredient_name": "Cukier",
                        "type": "Solid",
                        "id": 1,
                    },
                    "container_number": 3,
                }
            ],
        }
        response = self.client.get("/machine/containers/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data, machine_containers)

        # Edit wrong syntax
        edit = {"tea": "Syrop malinowy"}
        response = self.client.put(
            f'/machine/containers/ingredient/{data["ingredient_containers"][0]["id"]}/',
            edit,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

        # Edit tea to ingredient container
        edit = {"tea": {"tea_name": "Czarna herbata"}}
        response = self.client.put(
            f'/machine/containers/ingredient/{data["ingredient_containers"][0]["id"]}/',
            edit,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

        edit = {"id": 2}
        response = self.client.put(
            f'/machine/containers/ingredient/{data["ingredient_containers"][0]["id"]}/',
            edit,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/machine/containers/")
        self.assertEqual(response.status_code, 200)

    def test_create_delete_recipes(self):
        """
        Test creation and deletion of recipe
        """

        # No required fields
        recipe = {}
        response = self.client.post(
            "/recipes/", recipe, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

        recipe = {"ingredients": "", "recipe_name": "test1", "tea_type": ""}
        response = self.client.post(    
            "/recipes/", recipe, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

        recipe = {"ingredients": [{}], "recipe_name": "test1", "tea_type": [{}]}
        response = self.client.post(
            "/recipes/", recipe, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

        recipe = {
            "ingredients": [{"ammount": 14, "ingredient": {"ingredient_name": "fff"}}],
            "recipe_name": "test1",
            "tea_type": {"": ""},
        }
        response = self.client.post(
            "/recipes/", recipe, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

        recipe = {
            "ingredients": [
                {"ammount": 14, "ingredient": {"ingredient_name": "Cukier"}}
            ],
            "recipe_name": "test1",
            "tea_type": {"": ""},
        }
        response = self.client.post(
            "/recipes/", recipe, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

        id = Teas.objects.get(tea_name="Czarna herbata").id
        ing_id = Ingredients.objects.get(ingredient_name="Miód").id
        recipe = {
            "ingredients": [
                {"ammount": 14, "ingredient_id": ing_id}
            ],
            "recipe_name": "test1",
            "tea_type": id,
        }
        response = self.client.post(
            "/recipes/", recipe, content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)

        response = self.client.get("/recipes/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        response = self.client.delete(f"/recipes/{data[1]['id']}/")
        self.assertEqual(response.status_code, 204)

    def _edit_recipes(self):
        response = self.client.get("/recipes/")
        recipe = response.json()
        recipe[0]["descripction"] = "Nowa"

        response = self.client.get("/recipes/")
        recipe = response.json()

        # Empty PATCH nothing happens
        edit = {"ingredients": []}
        response = self.client.patch(
            f'/recipes/{recipe[0]["id"]}/', edit, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), recipe[0])

        # Patch with no id - error
        edit = {"ingredients": [{}]}
        response = self.client.patch(
            f'/recipes/{recipe[0]["id"]}/', edit, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

        # PATCH does not delete ingredients
        edit = {"ingredients": [{"id": recipe[0]["ingredients"][0]["id"]}]}
        response = self.client.patch(
            f'/recipes/{recipe[0]["id"]}/', edit, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), recipe[0])

        # Update ingredient ammount
        edit = {
            "ingredients": [{"id": recipe[0]["ingredients"][0]["id"], "ammount": 69}]
        }
        response = self.client.patch(
            f'/recipes/{recipe[0]["id"]}/', edit, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        recipe[0]["ingredients"][0]["ammount"] = 69
        self.assertEqual(response.json(), recipe[0])

        # Wrong ingredient
        edit = {
            "ingredients": [{"id": recipe[0]["ingredients"][0]["id"], "ingredient": {}}]
        }
        response = self.client.patch(
            f'/recipes/{recipe[0]["id"]}/', edit, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

        # Wrong ingredient name
        edit = {
            "ingredients": [
                {
                    "id": recipe[0]["ingredients"][0]["id"],
                    "ingredient": {"ingredient_name": "ffs"},
                }
            ]
        }
        response = self.client.patch(
            f'/recipes/{recipe[0]["id"]}/', edit, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

        # Succes edit
        edit = {
            "ingredients": [
                {
                    "id": recipe[0]["ingredients"][0]["id"],
                    "ingredient": {"ingredient_name": "Miód"},
                }
            ]
        }
        response = self.client.patch(
            f'/recipes/{recipe[0]["id"]}/', edit, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        recipe = self.client.get("/recipes/").json()
        self.assertEqual(response.json(), recipe[0])

    def test_get_recipe(self):
        response = self.client.get("/recipes/17/")

        compare_assert = {'id': 17, 'ingredients': [{'ammount': 12.5, 'ingredient': {'ingredient_name': 'Cukier', 'type': 'Solid', 'id': 21}, 'id': 27}, {'ammount': 3.33, 'ingredient': {'ingredient_name': 'Sok z cytryny', 'type': 'Liquid', 'id': 23}, 'id': 28}], 'tea_type': {'tea_name': 'Czarna herbata', 'id': 16}, 'voted': False, 'voted_score': 0, 'last_modification': None, 'descripction': 'Brak', 'recipe_name': 'test', 'score': 0.0, 'votes': 0, 'is_public': False, 'brewing_temperature': 80.0, 'brewing_time': 60.0, 'mixing_time': 15.0, 'is_favourite': False, 'tea_herbs_ammount': 15.0, 'tea_portion': 200.0, 'author': 6}
        
        data = response.json()
        data["last_modification"] = None
        self.assertEqual(data, compare_assert)


    def test_send_recipes(self):
        send_data = {
            "id": 1,
        }
        response = self.client.post("/send_recipe/", send_data, content_type="application/json")
        data = response.json()
        self.assertEqual(data, {'detail': 'Recipe does not exist.'})

        send_data = {
            "id": 26,
        }
        response = self.client.post("/send_recipe/", send_data, content_type="application/json")
        data = response.json()
        self.assertEqual(data, {'detail': ['Machine is not connected.', 'Mug is not ready.', 'Not enough tea herbs in container.', 'Given tea type is not available in your tea containers.', 'Not enough ingredient in container.', 'Ingredient Cukier, of required ammount: 12.5, is not avaible in your machine.', 'Ingredient Sok z cytryny, of required ammount: 3.33, is not avaible in your machine.', 'Not enough water.']})


        send_data = {
            "id": 27,
        }
        response = self.client.post("/send_recipe/", send_data, content_type="application/json")
        data = response.json()
        self.assertEqual(data, {'detail': ['Machine is not connected.', 'Mug is not ready.', 'Not enough tea herbs in container.', 'Given tea type is not available in your tea containers.', 'Ingredient Syrop malinowy, of required ammount: 27.33, is not avaible in your machine.', 'Not enough water.']})

        recipe_default = Recipes.objects.create(
            author=CustomUser.objects.get(pk=self.user.user_id),
            recipe_name="default",
            tea_type=Teas.objects.filter(tea_name="Zielona herbata")[0],
        )

        Machine.objects.filter(machine_id=self.user.machine).update(is_mug_ready=True, water_container_weight=3333, machine_status=2137)

        MachineContainers.objects.filter(Q(machine=self.user.machine) & Q(container_number__gte=2)).update(ammount='333')
        send_data = {
            "id": 29,
        }
        response = self.client.post("/send_recipe/", send_data, content_type="application/json")
        self.assertEqual(response.status_code, 200)

        return True

    def test_get_ingredients(self):
        ingredients_reference = [{'ingredient_name': 'Cukier', 'type': 'Solid', 'id': 9}, {'ingredient_name': 'Syrop malinowy', 'type': 'Liquid', 'id': 10}, {'ingredient_name': 'Sok z cytryny', 'type': 'Liquid', 'id': 11}, {'ingredient_name': 'Miód', 'type': 'Liquid', 'id': 12}]
        response = self.client.get("/ingredients/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data, ingredients_reference)
        return True

    def test_get_teas(self):
        data_reference = [{'tea_name': 'Czarna herbata', 'id': 19}, {'tea_name': 'Zielona herbata', 'id': 20}, {'tea_name': 'Biała herbata', 'id': 21}]
        response = self.client.get("/teas/")
        data = response.json()
        self.assertEqual(data, data_reference)
        return True

    def test_get_public_recipes(self):
        data_reference = {'count': 1, 'next': None, 'previous': None, 'results': [{'id': 16, 'ingredients': [{'ammount': 32.33, 'ingredient': {'ingredient_name': 'Sok z cytryny', 'type': 'Liquid', 'id': 19}, 'id': 25}, {'ammount': 13.33, 'ingredient': {'ingredient_name': 'Cukier', 'type': 'Solid', 'id': 17}, 'id': 26}], 'tea_type': {'tea_name': 'Czarna herbata', 'id': 13}, 'voted': False, 'voted_score': 0, 'last_modification': None, 'descripction': 'Brak', 'recipe_name': 'test2', 'score': 0.0, 'votes': 0, 'is_public': True, 'brewing_temperature': 80.0, 'brewing_time': 60.0, 'mixing_time': 15.0, 'is_favourite': False, 'tea_herbs_ammount': 15.0, 'tea_portion': 200.0, 'author': 5}]}
        response = self.client.get("/public_recipes/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        data["results"][0]["last_modification"] = None
        self.assertEqual(data, data_reference)
        return True

    def test_voting(self):
        example_recipe_id = 33

        # add new score

        data_score = {"score": 6}
        response = self.client.post(f"/recipes/{example_recipe_id}/vote/", data_score, content_type="application/json")        
        self.assertEqual(response.status_code, 400)

        data_score = {"score": -1}
        response = self.client.post(f"/recipes/{example_recipe_id}/vote/", data_score, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        
        data_score = {"score": 4}
        response = self.client.post(f"/recipes/{example_recipe_id}/vote/", data_score, content_type="application/json")
        self.assertEqual(response.status_code, 201)

        data_score = {"score": 1}
        response = self.client.post(f"/recipes/{example_recipe_id}/vote/", data_score, content_type="application/json")
        self.assertEqual(response.status_code, 400)

        response = self.client.get(f"/recipes/{example_recipe_id}/")
        recipe_reference = {'id': 33, 'ingredients': [{'ammount': 12.5, 'ingredient': {'ingredient_name': 'Cukier', 'type': 'Solid', 'id': 41}, 'id': 52}, {'ammount': 3.33, 'ingredient': {'ingredient_name': 'Sok z cytryny', 'type': 'Liquid', 'id': 43}, 'id': 53}], 'tea_type': {'tea_name': 'Czarna herbata', 'id': 31}, 'voted': False, 'voted_score': 0, 'last_modification': None, 'descripction': 'Brak', 'recipe_name': 'test', 'score': 4.0, 'votes': 1, 'is_public': False, 'brewing_temperature': 80.0, 'brewing_time': 60.0, 'mixing_time': 15.0, 'is_favourite': False, 'tea_herbs_ammount': 15.0, 'tea_portion': 200.0, 'author': 12}
        data = response.json()
        data['last_modification'] = None
        self.assertEqual(data, recipe_reference)

        # edit added score

        data_score = {"score":6}
        response = self.client.put(f"/recipes/{example_recipe_id}/vote/", data_score, content_type="application/json")
        self.assertEqual(response.status_code, 400)

        data_score = {"score":-1}
        response = self.client.put(f"/recipes/{example_recipe_id}/vote/", data_score, content_type="application/json")
        self.assertEqual(response.status_code, 400)

        recipe_reference["score"] = 5
        data_score = {"score":5}
        response = self.client.put(f"/recipes/{example_recipe_id}/vote/", data_score, content_type="application/json")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/recipes/{example_recipe_id}/")
        data = response.json()
        data['last_modification'] = None
        self.assertEqual(data, recipe_reference)
        
        return True
