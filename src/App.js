import React, { useState, useRef, useEffect } from 'react';
import './App.css';

function App() {
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState([]);
  const [isRephrasing, setIsRephrasing] = useState(false);
  const messagesEndRef = useRef(null);
  const [uploadStatus, setUploadStatus] = useState("");
  const [language, setLanguage] = useState("english");
  const [downloadLink, setDownloadLink] = useState("");

  const handleSendMessage = async () => {
    if (message) {
      setMessages((prevMessages) => [...prevMessages, { text: message, type: 'user' }]);
      setMessage('');

      try {
        const response = await fetch('http://127.0.0.1:5000/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ message: message, language: language }),
        });

        if (response.ok) {
          const data = await response.json();
          setMessages((prevMessages) => [
            ...prevMessages,
            { text: data.reply, type: 'llm' }, // Display the LLM response in the chat window
          ]);

          if (data.download_link) {
            setDownloadLink(data.download_link);
          }
        } else {
          console.error('Error from Flask server:', response.statusText);
        }
      } catch (error) {
        console.error('Failed to connect to Flask server:', error);
      }
    }
  };

  const handleRephraseQuestion = async () => {
    try {
      console.log("Rephrase button pressed");
      setIsRephrasing(true);
      
      // Optionally add a temporary message to show immediate feedback.
      setMessages((prevMessages) => [
        ...prevMessages,
        { text: "Rephrasing your question, please wait...", type: "assistant-loading" },
      ]);
      
      const response = await fetch("http://127.0.0.1:5000/rephrase", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });
      if (response.ok) {
        const data = await response.json();
        // Remove the temporary loading message
        setMessages((prevMessages) => prevMessages.filter(msg => msg.type !== "assistant-loading"));
        // Add the rephrased question to the messages
        setMessages((prevMessages) => [
          ...prevMessages,
          { text: data.reply, type: "assistant" },
        ]);
      } else {
        console.error("Error rephrasing question:", response.statusText);
      }
    } catch (error) {
      console.error("Failed to rephrase question:", error);
    } finally {
      setIsRephrasing(false);
    }
  };

  const handleChange = (event) => {
    setMessage(event.target.value);
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) {
      setUploadStatus("No file selected.");
      return;
    }
  
    setUploadStatus("Uploading...");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("http://127.0.0.1:5000/upload", {
        method: "POST",
        body: formData,
        headers: {
          "Language": language,
        },
      });

      const data = await response.json();
      if (response.ok) {
        setUploadStatus(`✅ File uploaded: ${file.name}`);
        setMessages((prevMessages) => [
          ...prevMessages,
          { text: `📂 Uploaded: ${file.name}`, type: "user" },
          { text: data.reply, type: "llm" },
        ]);
      } else {
        setUploadStatus(`❌ Upload failed: ${data.error}`);
      }
    } catch (error) {
      setUploadStatus("❌ Error uploading file.");
      console.error('Error uploading file:', error);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  return (
    <div className="App">
      <h1>Form Assistant</h1>
      <div className="chat-container">
        <div className="message-container">
          {messages.map((msg, index) => (
            <div
              key={index}
              className={
                msg.type === 'user'
                  ? 'user-message'
                  : msg.type === 'assistant-loading'
                  ? 'assistant-loading'
                  : 'LLM-message'
              }
            >
              {msg.text}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
  
        {/* 
           Updated input layout:
           1) A row with the text input and Send / I don't understand buttons.
           2) A row for Upload and Language.
        */}
        <div className="input-container">
          <div className="input-row">
            <input
              type="text"
              value={message}
              onChange={handleChange}
              placeholder="Type a message"
              onKeyDown={(event) => {
                if (event.keyCode === 13) {
                  handleSendMessage();
                }
              }}
            />
            <button onClick={handleSendMessage}>Send</button>
            <button onClick={handleRephraseQuestion} disabled={isRephrasing}>
              Explain
            </button>
          </div>
  
          <div className="input-row">
            <label className="upload-label">
              Upload
              <input
                type="file"
                className="file-upload"
                onChange={handleFileUpload}
              />
            </label>
            <input
              type="text"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              placeholder="Enter language (e.g., French)"
              className="language-input"
            />
          </div>
        </div>
  
        {uploadStatus && <p className="upload-status">{uploadStatus}</p>}
        {downloadLink && (
          <p className="download-link">
            <a href={`http://127.0.0.1:5000${downloadLink}`} download>
              Download Questions and Answers
            </a>
          </p>
        )}
      </div>
    </div>
  );
  
}

export default App;
