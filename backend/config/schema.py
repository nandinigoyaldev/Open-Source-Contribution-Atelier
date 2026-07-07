import graphene

import apps.content.schema


class Query(apps.content.schema.Query, graphene.ObjectType):
    # This class will inherit from multiple Queries as we begin to add more apps to the project
    pass


schema = graphene.Schema(query=Query)
