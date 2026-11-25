# Recommendation Agent

AI-powered personalized recommendation agent for B2B e-commerce.

**Hackathon:** ИИкузница — Софтлайн Решения  
**Track:** ИИ агент рекомендаций в личном кабинете  
**Status:** Prototype in development

## Overview

Recommendation Agent is a prototype of an intelligent recommendation system for a B2B e-commerce personal account.

The system analyzes customer context, purchase history, active licenses and available product information to generate personalized recommendations.

The primary business scenarios are:

- **Cross-sell:** recommend complementary products and services.
- **Up-sell:** recommend more advanced products or configurations.
- **Renewal:** identify opportunities for license and subscription renewal.

The solution combines a recommendation engine, business rules and AI-powered orchestration.

## Key Objectives

- Increase relevance of product recommendations.
- Identify cross-sell and up-sell opportunities.
- Improve customer retention and repeat purchases.
- Provide transparent explanations for recommendations.
- Keep recommendation generation measurable and cost-efficient.

## Architecture

The planned architecture consists of:

- API layer — application interface.
- Agent — workflow orchestration and tool execution.
- Recommendation Engine — candidate generation and ranking.
- Business Rules — validation and filtering.
- LLM Integration — context interpretation and recommendation explanations.
- Data Layer — customer, purchase, license and product information.

See [Architecture Overview](docs/architecture/overview.md).

## Technology Stack

Initial technology choices:

- Python
- FastAPI
- Pydantic
- Docker / Docker Compose
- LLM provider — TBD
- Database — TBD

## Project Structure

See the repository directory tree and documentation.

## Getting Started

Local setup instructions will be added as the application implementation progresses.

## Configuration

Copy `.env.example` to `.env` and configure the required environment variables.

Never commit API keys, passwords or other secrets.

## Development

Development guidelines, testing and deployment instructions will be documented here.

## Demo

A public demo environment will be available during the hackathon evaluation period.

## Documentation

- [Architecture](docs/architecture/overview.md)
- [Assumptions and Requirements](docs/requirements/assumptions.md)
- [Architecture Decisions](docs/decisions/)
- [Demo Scenario](docs/demo/demo-script.md)
- [Cost Estimation](docs/economics/cost-estimation.md)
- [Project State](STATE.md)

## Disclaimer

This repository contains a hackathon prototype. All synthetic data must be clearly identified as synthetic. External datasets, models and services are subject to their respective licenses and terms.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
