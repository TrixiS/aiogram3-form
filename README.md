# aiogram3-form
A library to create forms in aiogram3

# Example
```Python
# suppose you import here your router and bot objects
from aiogram import F, types

from aiogram3_form import Form, FormField


class NameForm(Form, router=your_router):
    first_name: str = FormField(enter_message_text="Enter your first name please")
    second_name: str = FormField(enter_message_text="Enter your second name please", filter=F.text.len() > 10)
    age: int = FormField(enter_message_text="Enter age as integer", error_message_text="Age should be numeric!")


@NameForm.submit()
async def name_form_submit_handler(form: NameForm, event_chat: types.Chat):
    # handle form data
    # also supports aiogram standart DI (e. g. middlewares, filters, etc)
    await bot.send_message(
        event_chat.id, f"Your full name is {form.first_name} {form.second_name}!"
    )
    
    
@router.message(F.text == "/form")
async def form_handler(message: types.Message, state: FSMContext):
    await NameForm.start(state)  # start your form
```

After submit callback call the state would be automatically cleared.

You can control this state using the following metaclass kwarg

```Python
...


class NameForm(Form, clear_state_on_submit=False):  # True by default
    ...


@NameForm.submit()
async def name_form_submit_handler(form: NameForm, state: FSMContext):
    # so you can set your exit state manually
    await state.set_state(...)
```
