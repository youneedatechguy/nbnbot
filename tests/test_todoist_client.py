import pytest
import pytest_asyncio
from app.todoist_client import TodoistClient, TodoistTask


@pytest.mark.asyncio
async def test_create_task():
    client = TodoistClient("", mock_mode=True)
    
    task = await client.create_task(content="Test task", due_string="tomorrow")
    
    assert task.content == "Test task"
    assert task.id.startswith("mock_")


@pytest.mark.asyncio
async def test_get_tasks():
    client = TodoistClient("", mock_mode=True)
    
    await client.create_task("Task 1")
    await client.create_task("Task 2")
    
    tasks = await client.get_tasks()
    
    assert len(tasks) == 2


@pytest.mark.asyncio
async def test_complete_task():
    client = TodoistClient("", mock_mode=True)
    
    task = await client.create_task("Complete me")
    result = await client.complete_task(task.id)
    
    assert result is True


@pytest.mark.asyncio
async def test_delete_task():
    client = TodoistClient("", mock_mode=True)
    
    task = await client.create_task("Delete me")
    result = await client.delete_task(task.id)
    
    assert result is True
    
    tasks = await client.get_tasks()
    assert len(tasks) == 0