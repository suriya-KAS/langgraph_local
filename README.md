# 🤖 MySellerCentral Chatbot

> Your friendly AI assistant that helps e-commerce sellers manage their online business like a pro!

## What is This?

Imagine having a smart assistant that knows everything about MySellerCentral - the e-commerce platform that helps sellers manage their online stores across multiple marketplaces like Amazon, ONDC, and eBay. This chatbot is like having that expert sitting right next to you, ready to answer questions 24/7!

Whether you're wondering about pricing plans, need help with AI-powered tools, want to know which marketplaces are supported, or just need a quick guide on how things work - this chatbot has got your back. It speaks multiple languages, remembers your conversations, and can even help you with wallet transactions and currency conversions.

## ✨ What Can It Do?

### 🗣️ **Smart Conversations**
- Ask questions in plain English (or Spanish, Hindi, French, German!)
- Get instant, accurate answers from a comprehensive knowledge base
- Maintains context throughout your conversation - it remembers what you talked about
- Understands your intent and provides relevant, structured responses

### 💰 **Wallet & Payments**
- Check your wallet balance
- View transaction history
- Get help with currency conversions
- Understand pricing for AI agents and services

### 🤖 **AI Agent Information**
- Learn about all 9+ specialized AI agents available
- Get pricing details (pay-per-use basis)
- Understand what each agent can do for your business
- Find out which marketplaces each agent supports

### 🛒 **Marketplace Support**
- Discover which marketplaces are integrated (Amazon, ONDC, eBay, and more)
- Get help with marketplace-specific features
- Learn about ONDC integration and benefits
- Understand workflow automation options

### 📊 **Rich Responses**
- Get beautifully formatted answers with tables, lists, and structured data
- Receive actionable suggestions and recommendations
- See relevant links and resources when available
- Get step-by-step guidance for complex tasks

## 🚀 Quick Start Guide

### Step 1: Get Everything Ready

First, make sure you have:
- **Python 3.8 or newer** installed on your computer
- An **AWS account** with access to Bedrock (the AI brain behind this chatbot)
- A **Bedrock Knowledge Base** already set up (this contains all the information the chatbot knows)

### Step 2: Set Up the Project

1. **Download the code** (if you haven't already):
   ```bash
   git clone <repository-url>
   cd PROTOTYPE
   ```

2. **Create a virtual environment** (think of it as a clean workspace):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install the required tools**:
   ```bash
   pip install -r requirements.txt
   ```


### Step 3: Start the Chatbot

You have two ways to use the chatbot:

#### Option A: Use the API (For Developers)
Perfect if you want to integrate this chatbot into your own app or website.

```bash
python main.py
```

Once running, you can:
- Access the API at `http://localhost:8502`
- View interactive documentation at `http://localhost:8502/docs`
- Test endpoints using the built-in Swagger UI

#### Option B: Use the Web Interface (For Everyone)
A beautiful, WhatsApp-style chat interface that's super easy to use.

```bash
streamlit run src/app.py
```

Then open your browser to `http://localhost:8501` and start chatting!

## 📁 What's Inside?

Here's a quick tour of the project structure:

```
PROTOTYPE/
├── src/                    # The main code lives here
│   ├── api/               # API endpoints (how the chatbot talks to other apps)
│   ├── core/              # The brain - AI integration and models
│   ├── services/          # Special services (wallet, agents, currency)
│   └── app.py             # The web interface
├── database/              # Database models for storing conversations
├── utils/                 # Helper tools (logging, etc.)
├── docs/                  # Documentation and API guides
├── tests/                 # Tests to make sure everything works
├── main.py                # The starting point for the API
└── requirements.txt       # List of all the tools needed
```

## 🎯 How to Use

### For End Users (Using the Web Interface)

1. Start the Streamlit app (see Step 3, Option B above)
2. Open the web interface in your browser
3. Type your question in the chat box
4. Get instant answers!

**Example questions you can ask:**
- "What AI agents are available?"
- "Show me pricing plans"
- "Which marketplaces do you support?"
- "Tell me about ONDC integration"
- "How do I check my wallet balance?"

### For Developers (Using the API)

Send a POST request to `/api/chat/message` with your question:

```bash
curl -X POST "http://localhost:8502/api/chat/message" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What AI agents are available?",
    "conversationId": "unique-conversation-id",
    "context": {
      "userId": "user123",
      "clientInfo": {
        "device": "desktop",
        "appVersion": "1.0.0",
        "timezone": "Asia/Kolkata"
      }
    },
    "language": "English"
  }'
```

Check out `docs/CURL_EXAMPLES.md` for more examples!

## 🔧 Configuration

The chatbot needs a few things to work properly. Create a `.env` file with:

- `AWS_ACCESS_KEY_ID` - Your AWS access key
- `AWS_SECRET_ACCESS_KEY` - Your AWS secret key
- `AWS_DEFAULT_REGION` - AWS region (usually `us-east-1`)
- `BEDROCK_KNOWLEDGE_BASE_ID` - Your Bedrock Knowledge Base ID
- `WALLET_SERVICE_URL` - (Optional) URL for wallet microservice
- `MONGODB_URI` - (Optional) MongoDB connection string for storing conversations

**⚠️ Important:** Never commit your `.env` file to version control! It contains sensitive information.

## 📊 Logging

The chatbot keeps detailed logs of everything that happens. You can find them in the `logs/` folder, organized by date and time. This helps with debugging and understanding what's going on behind the scenes.

## 🧪 Testing

Want to make sure everything works? Run the tests:

```bash
python -m pytest tests/
```

## 📚 Need More Details?

We've got comprehensive documentation for everything:

- **API Documentation** (`docs/API_DOCUMENTATION.md`) - Complete API reference
- **API Structure** (`docs/API_STRUCTURE.md`) - How requests and responses work
- **CURL Examples** (`docs/CURL_EXAMPLES.md`) - Ready-to-use API examples
- **Deployment Guide** (`DEPLOYMENT.md`) - How to deploy to production

## 🚀 Deploying to Production

Ready to go live? Check out `DEPLOYMENT.md` for step-by-step instructions on:
- Setting up a production server
- Configuring system services
- Setting up reverse proxy with Nginx
- Adding SSL certificates for secure connections
- Monitoring and maintenance tips

## 🛠️ For Developers: Adding New Features

Want to extend the chatbot? Here's how:

1. **Add a new service?** Put it in `src/services/`
2. **Add a new API endpoint?** Add it to `src/api/routes.py`
3. **Change data models?** Update `src/core/models.py`
4. **Add tests?** Put them in `tests/`

The code is organized to make it easy to add new features without breaking existing ones!

## 🔐 Security Best Practices

- ✅ Never commit `.env` files
- ✅ Keep AWS credentials secure
- ✅ Use environment variables for all sensitive data
- ✅ Regularly rotate AWS access keys
- ✅ Give AWS IAM users only the minimum permissions they need
- ✅ Use HTTPS in production

## 🤝 Contributing

Found a bug? Have an idea? Want to help improve the chatbot?

1. Create a feature branch
2. Make your changes
3. Add tests for new features
4. Submit a pull request

We'd love to have your contributions!

## 📞 Need Help?

Having trouble? Questions? Just want to chat?

- **Email:** sales@mysellercentral.com
- **Check the docs:** Look in the `docs/` folder
- **Check the logs:** See what's happening in `logs/`

## 📄 License

Copyright © 2024 MySellerCentral

---

## 🎉 That's It!

You're all set! The chatbot is ready to help you and your users navigate MySellerCentral with ease. Whether you're a seller looking for quick answers or a developer building something awesome, this chatbot is here to make your life easier.

Happy chatting! 🚀
