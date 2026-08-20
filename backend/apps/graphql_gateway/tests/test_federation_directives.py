import pytest
from graphql import parse
from backend.apps.graphql_gateway.federation import transform_query_ast

def test_nested_field_directives_are_preserved():
    query_string = """
        query DeepQuery {
            user @auth(role: "ADMIN") {
                profile @sensitiveData {
                    settings @complexity(value: 5) {
                        theme
                    }
                }
            }
        }
    """
    ast = parse(query_string)
    transformed_ast = transform_query_ast(ast)
    
    definitions = transformed_ast.definitions
    field_selection_set = definitions[0].selection_set.selections
    
    user_field = field_selection_set[0]
    assert len(user_field.directives) == 1
    assert user_field.directives[0].name.value == "auth"
    
    profile_field = user_field.selection_set.selections[0]
    assert len(profile_field.directives) == 1
    assert profile_field.directives[0].name.value == "sensitiveData"

    settings_field = profile_field.selection_set.selections[0]
    assert len(settings_field.directives) == 1
    assert settings_field.directives[0].name.value == "complexity"
