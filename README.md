# aiogram3-form

A library for creating forms in aiogram3

```shell
pip install aiogram3-form
```

## What is a form?

Form is a set of fields that you want your user to fill in. Forms are defined as classses derived from `aiogram3_form.Form` and contain fields with annotated types and `aiogram3_form.FormField` values. You should not inherit your form class from your another form class. (so no deep inheritance).

When you start your form with `.start()` method, your bot will ask a user input values one by one until the end. Reaching the last field of a form means "submitting" it.

Forms use default aiogram FSM.

## Minimal example

```Python
import asyncio

from aiogram import Bot, Dispatcher, F, Router
from aiogram3_form import Form, FormField
from aiogram.fsm.context import FSMContext

bot = Bot(token="YOUR_TOKEN")
dispatcher = Dispatcher()
router = Router()
dispatcher.include_router(router)


class NameForm(Form):
    first_name: str = FormField(enter_message_text="Enter your first name please")
    second_name: str = FormField(
        enter_message_text="Enter your second name please",
        filter=(F.text.len() > 10) & F.text,
    )
    age: int = FormField(enter_message_text="Enter age as integer")


@NameForm.submit(router=router)
async def name_form_submit_handler(form: NameForm):
    # handle form submitted data
    # also supports aiogram standart DI (e. g. middlewares, filter data, etc)
    # you can do anything you want in here
    await form.answer(f"{form.first_name} {form.second_name} of age {form.age}")


@router.message(F.text == "/form")
async def form_handler(_, state: FSMContext):
    await NameForm.start(bot, state)  # start your form


asyncio.run(dispatcher.start_polling(bot))
```

## Keyboards

You can use any type of keyboard in your form, but only reply keyboards are actually useful. (cause forms only accept messages as input, so no callback queries)

```Python
FRUITS = ("Orange", "Apple", "Banana")

fruits_markup = (
    ReplyKeyboardBuilder().add(*(KeyboardButton(text=f) for f in FRUITS)).as_markup()
)


class FruitForm(Form):
    fruit: str = FormField(
        enter_message_text="Pick your favorite fruit",
        filter=F.text.in_(FRUITS) & F.text,
        reply_markup=fruits_markup,
    )
```

## Form filters

Default filters are built in for types: `str` (check for mesasge text and returns it), `int` (tries to convert message text to int), `float`, `datetime.date`, `datetime.datetime`, `aiogram.types.PhotoSize`, `aiogram.types.Document`, `aiogram.types.Message`

Supported form filter kinds: sync function, async function, aiogram magic filter.

If your filter is a function (sync or async), it should take `aiogram.types.Message` as the first argument and return `False`, if it does not pass. If a filter passed, it should return the value you want in your form data.

Magic filters return `None` on failure, so it's a special case that is handled differently.

If your filter fails and `error_message_text` is provided in `FormField` call, an error message will be sent with the provided text.

```Python
def sync_fruit_form_filter(message: types.Message) -> str:
    if message.text not in FRUITS:
        return False

    return message.text


async def async_fruit_form_filter(
    message: types.Message,
): ...  # some async fruit filtering


class FruitForm(Form):
    fruit: str = FormField(
        enter_message_text="Pick your favorite fruit",
        filter=sync_fruit_form_filter,  # you can pass an async filter here as well
        reply_markup=fruits_markup,
        error_message_text="Thats an invalid fruit",
    )
```

## Enter callback

Enter callbacks enable you to write your own enter functions for form fields

```Python
async def enter_fruit_callback(chat_id: int, user_id: int, data: dict[str, Any]):
    # do whatever you want in here
    print(f"user {user_id} has just entered the fruit callback in chat {chat_id}!")

    return await bot.send_message(
        chat_id, "Hey, pick your favorite fruit please", reply_markup=fruits_markup
    )


class FruitForm(Form):
    fruit: str = FormField(
        enter_callback=enter_fruit_callback,
        filter=sync_fruit_form_filter,
        error_message_text="Thats an invalid fruit",
    )
```
