class SystemArchitectAgent:

    def run(self, requirements):

        architecture = {
            "frontend": "React.js",
            "backend": "FastAPI",
            "database": "PostgreSQL",
            "deployment": "Docker + GCP"
        }

        return architecture


if __name__ == "__main__":
    agent = SystemArchitectAgent()

    sample_requirements = {
        "project": "AI chatbot",
        "users": ["customer", "admin"],
        "features": ["chat", "knowledge search"]
    }

    result = agent.run(sample_requirements)

    print("Generated Architecture:")
    print(result)