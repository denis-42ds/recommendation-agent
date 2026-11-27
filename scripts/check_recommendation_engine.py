# smoke test

from recommendation_agent import load_recommendation_data

DATA = load_recommendation_data(
    workbook_path="docs/source-materials/Датасет_Рекомендации_ЛК_v5.xlsx",
)

print("Clients:", len(DATA.client_groups))
print("Clients with history:", len(DATA.histories))

client_id = next(
    client_id
    for client_id, history in DATA.histories.items()
    if history
)

result = DATA.recommend_for_client(client_id, k=3)

print("Client:", client_id)
print("Group:", result.client_group)
print("Personalized:", result.personalized)
print("Fill rate:", result.fill_rate)

for recommendation in result.recommendations:
    print(recommendation.to_dict())
